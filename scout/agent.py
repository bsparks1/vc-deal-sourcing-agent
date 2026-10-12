# The Scout agent: a LangGraph ReAct loop where Claude decides which tool to call next
# (search, read, check, score, save), sees the result, and repeats until the job is done.
# run_agent() is the one entry point: the terminal script calls it now, the UI in Step 6.

from typing import Callable

from langchain_anthropic import ChatAnthropic
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent

from scout import companies, config, db, feedback
from scout.defaults import DEFAULT_FUND_PROFILE
from scout.tools import (check_watchlist, read_page, research_founders, save_candidate,
                         score_against_thesis, search_web)
from scout.tracing import setup_tracing

TOOLS = [search_web, read_page, check_watchlist, research_founders, score_against_thesis,
         save_candidate]

SYSTEM_PROMPT = """You are Scout, a venture analyst who finds very early-stage companies
for one fund. You research the web on your own using your tools.

FUND PROFILE
Fund: {fund_name}
Thesis: {thesis}
Target categories:
{categories}
Stages: {stages}
Check size: {check_size}
Signals to look for:
{include_signals}
Signals that rule a company out:
{exclude_signals}

HOW TO WORK
1. Use search_web to find candidate companies. Prefer searches that surface small, new
   brands (launch announcements, local press, founder interviews, "new brand" roundups),
   not market overviews, which mostly list famous brands.
2. For each candidate, call check_watchlist first. Skip any that are already saved.
3. Drop obviously established companies right away, without scoring them: anything you
   recognize as well known, in national retail, or with a priced VC round.
4. Research the rest with read_page. Before scoring, you must have found the company's own
   website AND at least one source showing how early it is (launch date, funding, retail
   footprint, or follower count). If you can't find both, skip the company. Never score or
   save a company you know almost nothing about.
5. Call research_founders for the company. Then call score_against_thesis with every fact
   you found (including the founders) and the source URL for each.
6. If the score is {min_score} or higher, call save_candidate, including concrete traction
   signals (follower counts, retailers, reviews, press) you saw. If it's lower, move on.
7. Stop when you have saved {target} companies, then reply with a short summary of each
   one saved (name, score, one line on why) and anything you skipped and why.

RULES
- Never invent facts. Every fact must come from a page or search result you saw.
- When uncertain whether a company is truly early-stage, skip it.
{learned_section}"""

# Added to the prompt only once the fund has reviewed some companies (Step 7).
LEARNED_SECTION = """
WHAT THIS FUND HAS TAUGHT YOU (from its thumbs up / down on past results)
{preferences}
Use this to decide what to search for and which candidates to skip. The fund profile and
rules above still come first.
"""


def build_system_prompt(profile: dict, target: int, preferences: str | None = None) -> str:
    """Fill the fund profile, run settings, and learned preferences into the instructions."""
    fields = ["fund_name", "thesis", "categories", "stages", "check_size",
              "include_signals", "exclude_signals"]
    # "or 'not specified'" avoids blank lines (or "None") in the prompt for empty fields.
    values = {field: profile.get(field) or "not specified" for field in fields}
    learned = LEARNED_SECTION.format(preferences=preferences) if preferences else ""
    return SYSTEM_PROMPT.format(**values, target=target, min_score=config.MIN_SAVE_SCORE,
                                learned_section=learned)


def build_agent(profile: dict, target: int, preferences: str | None = None):
    """Create the LangGraph ReAct agent: Claude + the tools + the system prompt."""
    llm = ChatAnthropic(
        model=config.MODEL,
        api_key=config.ANTHROPIC_API_KEY,
        max_tokens=config.AGENT_MAX_TOKENS,
        # Same safety-filter fallback as scoring.py (see the comment there).
        betas=["server-side-fallback-2026-07-01"],
        model_kwargs={"fallbacks": "default"},
    )
    # create_react_agent builds the loop: call the model -> if it asked for tools, run them
    # and send the results back -> repeat until the model replies without a tool call.
    return create_react_agent(llm, TOOLS, prompt=build_system_prompt(profile, target, preferences))


def describe_step(message) -> str | None:
    """Turn one message from the agent's stream into a short progress line (or None)."""
    if getattr(message, "tool_calls", None):  # the model decided to call tools
        calls = [f"{call['name']}({', '.join(f'{v!r}'[:60] for v in call['args'].values())})"
                 for call in message.tool_calls]
        return "→ " + "; ".join(calls)
    if message.type == "tool":  # a tool finished; show the first part of its result
        return f"  ← {message.name}: {str(message.content)[:120]}"
    return None


def run_agent(target: int = 3, focus: str = "", on_step: Callable[[str], None] = print,
              trigger: str = "manual") -> dict:
    """Run the agent once to find `target` new companies, optionally with a focus.

    Records the run in the runs table, reports progress through on_step (print by default;
    the UI will pass its own function), and returns the run's id, status, and summary.
    """
    config.require_keys()
    tracing_on = setup_tracing()  # if Phoenix is running, every step shows up there
    db.init_db()

    request = f"Find {target} new companies" + (f" focused on: {focus}" if focus else "")
    run_id = companies.create_run(request, trigger)  # trigger: 'manual' or 'scheduled' (Step 12)
    profile = db.get_fund_profile() or DEFAULT_FUND_PROFILE
    learned = feedback.get_learned_preferences()  # None until the fund reviews something
    agent = build_agent(profile, target, learned["summary"] if learned else None)

    run_settings = {
        "recursion_limit": config.AGENT_MAX_STEPS,  # hard stop so a run can't loop forever
        "configurable": {"run_id": run_id},  # passed through to save_candidate
    }
    summary, status, error = "", "completed", None
    try:
        # stream_mode="updates" yields after each step, so we can show progress live.
        for update in agent.stream({"messages": [("user", request)]}, run_settings,
                                   stream_mode="updates"):
            for step in update.values():
                for message in step.get("messages", []):
                    line = describe_step(message)
                    if line:
                        on_step(line)
                    elif message.type == "ai":
                        summary = message.text  # the model's final answer (no tool calls)
    except GraphRecursionError:
        status, error = "stopped", f"Hit the {config.AGENT_MAX_STEPS}-step limit."
    except Exception as exc:
        status, error = "failed", str(exc)

    saved = companies.finish_run(run_id, status, error)
    return {"run_id": run_id, "status": status, "companies_saved": saved,
            "summary": summary, "error": error, "tracing_on": tracing_on}
