# The tools the agent can call: research the web (search_web, read_page), avoid repeats
# (check_watchlist), look up the team (research_founders), judge a company
# (score_against_thesis), and save it (save_candidate).
# Each tool is a normal Python function wrapped with LangChain's @tool decorator, which
# turns its name, arguments, and docstring into a description the model reads.

import json
import sqlite3

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from scout import companies, config, db
from scout.defaults import DEFAULT_FUND_PROFILE
from scout.founders import research_founders as find_founders
from scout.scoring import score_company
from scout.web import get_tavily_client


# Note: for @tool functions, the docstring is also the instruction the model sees,
# so it is written for the model: what the tool does and when to use it.
# [A3 Tools] One of the six tools the agent can call (see TOOLS in scout/agent.py).
@tool
def search_web(query: str) -> dict:
    """Search the web and return the top results (title, url, snippet) for a query.

    Use this to discover companies and find pages worth reading. Snippets are short;
    call read_page on a result's url to get the full text before relying on details.
    """
    try:
        response = get_tavily_client().search(
            query=query,
            max_results=config.SEARCH_MAX_RESULTS,
            search_depth=config.SEARCH_DEPTH,  # a fast mode: discovery doesn't need more
        )
    # [A4 Tool results] Errors come back as data, not crashes, so the agent can adapt.
    except Exception as error:
        # Return the error instead of crashing, so the agent can see what went wrong
        # and try a different query (one failed search shouldn't end a whole run).
        return {"query": query, "error": f"Search failed: {error}"}

    # Keep only the fields the agent needs; Tavily returns extra metadata we'd pay tokens for.
    results = [
        # Snippets are cut short: they only need to say whether a page is worth reading.
        {"title": r.get("title", ""), "url": r.get("url", ""),
         "snippet": r.get("content", "")[: config.SNIPPET_MAX_CHARS]}
        for r in response.get("results", [])
    ]
    return {"query": query, "results": results}


@tool
def read_page(url: str) -> dict:
    """Read a web page and return its main text content.

    Use this on a promising url from search_web (a company's website, an About page,
    a news article) to get the facts you need. Long pages are cut off at a fixed length.
    """
    try:
        response = get_tavily_client().extract(urls=[url], format="text")
    except Exception as error:
        return {"url": url, "error": f"Could not read page: {error}"}

    # Tavily puts pages it could read in "results" and pages it couldn't in "failed_results".
    pages = response.get("results", [])
    if not pages:
        return {"url": url, "error": "Could not read page (it may block bots or require a login)."}

    text = pages[0].get("raw_content") or ""
    truncated = len(text) > config.PAGE_MAX_CHARS
    return {
        "url": url,
        "content": text[: config.PAGE_MAX_CHARS],
        # Tells the agent (and you, in traces) that the page was longer than what it saw.
        "truncated": truncated,
    }


# Scores from score_against_thesis, keyed by domain. save_candidate reads the score from
# here, so the agent can't save a company it never scored, or type in a made-up score.
# (Kept in memory: fine for one process; it resets when the app restarts.)
# [A8 State] Tool-side state the model can't edit: save_candidate reads the real score here.
SCORES: dict[str, dict] = {}
# Same idea for founders: save_candidate stores the researched (source-checked) founders,
# not names the agent typed in itself.
FOUNDERS: dict[str, list[dict]] = {}


@tool
def check_watchlist(name_or_domain: str) -> dict:
    """Check whether a company is already saved, by its name or website domain.

    Call this as soon as you find a candidate, before researching it further, so you
    don't spend time on companies the fund has already seen.
    """
    company = companies.find_company(name_or_domain)
    if company is None:
        return {"already_saved": False}
    return {"already_saved": True, "name": company["name"], "status": company["status"]}


@tool
def research_founders(company_name: str, domain: str, extra_urls: list[str] | None = None) -> dict:
    """Find the company's founders: names, roles, and backgrounds, each with source URLs.

    Call this for every company you plan to score, after confirming it's early-stage and
    before score_against_thesis, then include what it found in the facts you pass for
    scoring (it informs the team score). If you already read pages that name a founder,
    pass their URLs in extra_urls (up to 3) so they're checked too. Founders are saved
    automatically by save_candidate.
    """
    try:
        result = find_founders(company_name, domain, extra_urls)
    except Exception as error:
        return {"error": f"Founder research failed: {error}"}
    FOUNDERS[companies.normalize_domain(domain)] = result["founders"]
    return result


# [A7 Specialist LLM calls] The agent delegates judgment to a separate, focused LLM call
# (scoring.py) with its own rubric and fixed output shape, instead of scoring in its head.
@tool
def score_against_thesis(company_name: str, domain: str, company_facts: str) -> dict:
    """Score a company 0-100 against the fund's thesis and rubric.

    Call this once you have researched a company. Pass its name, its website domain
    (e.g. "example.com"), and everything you learned as plain text: what it makes, launch
    date, funding, retail footprint, follower counts, founders, and the source URL for each
    fact. Returns the total score, a per-dimension breakdown, a rationale, and any
    exclusion signals found.
    """
    # Use the fund's saved profile; fall back to the template if none has been saved yet.
    profile = db.get_fund_profile() or DEFAULT_FUND_PROFILE
    try:
        result = score_company(f"Name: {company_name}\nDomain: {domain}\n{company_facts}", profile)
    except Exception as error:
        # Same pattern as the web tools: report the problem instead of ending the run.
        return {"error": f"Scoring failed: {error}"}

    SCORES[companies.normalize_domain(domain)] = result
    return result


@tool
def save_candidate(
    name: str,
    domain: str,
    one_liner: str,
    sources: list[str],
    run_config: RunnableConfig,
    category: str | None = None,
    stage: str | None = None,
    location: str | None = None,
    founded_year: int | None = None,
    funding_summary: str | None = None,
    traction: list[str] | None = None,
) -> dict:
    """Save a scored company to the fund's review queue (they review it in Explore).

    Only call this after score_against_thesis for the same domain. one_liner is one
    sentence on what the company makes. sources is the list of URLs your facts came from.
    traction is a list of concrete signals with numbers where possible, like
    ["~3,200 Instagram followers", "Stocked in 2 Portland co-ops"]. Founders from
    research_founders are added automatically. Leave any field you couldn't verify empty
    rather than guessing.
    """
    # run_config is filled in by LangGraph, not the model (LangChain spots the RunnableConfig
    # type and hides it from the model). It carries the current run's id.
    # [A8 State] run_config is injected by LangGraph and hidden from the model (not a tool argument).
    run_id = run_config["configurable"].get("run_id")
    key = companies.normalize_domain(domain)

    # [A5 Guardrails in code] Deterministic checks around the LLM: no score, low score, or no
    # sources means no save, whatever the model says. Refusals go back as data so it moves on.
    # Hard rules live in code, not just in the prompt (the lesson from Step 4).
    score = SCORES.get(key)
    if score is None:
        return {"saved": False, "reason": "Score this company with score_against_thesis first."}
    if score["score_total"] < config.MIN_SAVE_SCORE:
        return {"saved": False, "reason": f"Score {score['score_total']} is below the minimum "
                f"of {config.MIN_SAVE_SCORE}. Move on to another company."}
    if not sources:
        return {"saved": False, "reason": "Add the source URLs your facts came from."}

    try:
        company_id = companies.save_company({
            "name": name, "domain": key, "website": f"https://{key}", "one_liner": one_liner,
            "category": category, "stage": stage, "location": location,
            "founded_year": founded_year, "funding_summary": funding_summary,
            # Lists and dicts are stored as JSON text (SQLite has no list type).
            "founders": json.dumps(FOUNDERS.get(key, [])), "sources": json.dumps(sources),
            "traction": json.dumps(traction or []),
            "score_total": score["score_total"],
            "score_breakdown": json.dumps(score["score_breakdown"]),
            "rationale": score["rationale"], "run_id": run_id,
        })
    except sqlite3.IntegrityError:
        return {"saved": False, "reason": "This domain is already saved."}
    return {"saved": True, "company_id": company_id, "score_total": score["score_total"]}
