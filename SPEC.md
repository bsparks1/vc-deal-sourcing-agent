# Scout: an agentic deal-sourcing analyst for VC funds

## What it is
Scout is a web app a venture fund uses to find early-stage companies that match its thesis.
The fund describes what it invests in. An AI agent then researches the web on its own:
it decides what to search, which pages to read, which companies are too established, and
how well each one fits. The fund reviews what the agent found, saves the good ones to a
watchlist, and gives thumbs up / thumbs down feedback that the agent learns from on the next run.

Origin: v1 (the `bp-sourcing` repo) was a fixed scraping pipeline for Brand Project, a CPG fund.
Its biggest problem was surfacing established brands (e.g. Poppi) as "emerging". v2 replaces the
fixed pipeline with an agent, and adds tracing and evals (Arize Phoenix) so failures are visible
and measurable instead of found by eyeballing the database.

## Who uses it
An investor or analyst at a seed / pre-seed fund. One fund per install for now.

## User stories
1. As an investor, I can enter my fund's thesis, target categories, stages, check size,
   and signals to include / exclude, so the agent knows what "good" looks like.
2. As an investor, I can ask the agent to "find N new companies" (optionally with a focus,
   e.g. "functional beverages"), watch it work, and get a ranked list with scores and reasons.
3. As an investor, I can give each result a thumbs up / down with a short reason, and the
   next run reflects what I liked and disliked.
4. As an investor, I can save companies to a watchlist and see them on a dashboard.
5. As an investor, I can open a company and see everything known about it: what it makes,
   stage and funding, traction signals, founding team backgrounds, score breakdown, and sources.
6. As an investor, I can set a cadence ("3 new companies every day") and see new ones appear.
7. As an investor, I can see what changed on watchlist companies since they were saved.
8. As the builder, I can open Phoenix and see every step the agent took for any run.

## Phases
- **Phase 1 (interview core):** stories 1-4 and 8.
- **Phase 2:** story 5 (deep profile + founders) and evals.
- **Phase 3:** stories 6-7 (cadence, change tracking).
- **Later:** multiple funds, logins, email alerts, deployment.

## Tech stack (and why)
| Piece | Choice | Why |
|---|---|---|
| Language | Python 3.12 (managed by `uv`) | Agent frameworks and Arize/Phoenix are Python-first |
| Agent framework | LangGraph (`create_react_agent`) | Standard ReAct loop (reason, act, observe) in very little code; auto-traced by Phoenix |
| Model | Claude via `langchain-anthropic` | Strong at tool use and following a detailed rubric |
| Web search + page reading | Tavily | Built for agents: one API for search and extraction, returns clean text |
| Web UI | Streamlit | A full web app in plain Python, no separate frontend |
| Storage | SQLite (one file, `scout.db`) | Zero setup, easy to inspect, enough for one fund |
| Observability | Arize Phoenix (local) + OpenInference | Traces every LLM call and tool call; runs evals |

## Architecture
```
 Streamlit UI (app.py + pages/)
   Fund Profile | Source | Inbox | Watchlist | Company detail
          |                      ^
          v                      | reads/writes
   scout/agent.py  ----------> scout/db.py (SQLite: scout.db)
     LangGraph ReAct agent
     system prompt = fund profile + learned preferences + rules
          |
          v  decides which tools to call, in what order, how many times
   scout/tools.py
     search_web(query)               -> Tavily search
     read_page(url)                  -> Tavily extract
     check_watchlist(name_or_domain) -> already seen? (SQLite)
     score_against_thesis(facts)     -> scout/scoring.py (separate LLM call, structured output)
     save_candidate(...)             -> writes a company to the inbox (SQLite)
     research_founders(company)      -> Phase 2
          |
   scout/tracing.py: Phoenix + OpenInference auto-instrumentation (every step is a span)
```

## Data model (SQLite)
- **fund_profile**: id, fund_name, thesis, categories, stages, check_size, include_signals,
  exclude_signals, daily_target, updated_at. (One row in Phase 1.)
- **companies**: id, name, domain (unique), website, one_liner, category, stage, location,
  founded_year, funding_summary, founders (JSON text), score_total, score_breakdown (JSON text),
  rationale, sources (JSON list of URLs), status (`new` | `watching` | `passed`), run_id,
  created_at, updated_at.
- **feedback**: id, company_id, verdict (`up` | `down`), reason, created_at.
- **runs**: id, request, started_at, finished_at, companies_saved, status, error.

## Scoring rubric (default, 100 points)
| Dimension | Max | What it measures |
|---|---|---|
| thesis_fit | 30 | Category and product match the fund's thesis |
| stage_fit | 25 | Truly early: little/no outside funding, small footprint, recent launch. Heavily penalize established companies |
| product | 20 | Differentiation, quality signals |
| team | 15 | Founder-market fit, relevant background (neutral if unknown) |
| market | 10 | Category growth and tailwinds |
"When uncertain, score neutral; never invent facts. Every claim must come from a source URL."

## How the agent learns from feedback
After each thumbs up/down, `scout/feedback.py` summarizes all feedback into a short
"learned preferences" paragraph (one LLM call). That paragraph is added to the agent's system
prompt on the next run. This is in-context learning: no model training, fully visible in traces.

## Default fund profile (template, from v1)
Brand Project, pre-seed/seed CPG. Targets: functional food & beverage, better-for-you snacks,
indie beauty & personal care, supplements & wellness. Include signals: under ~10k Instagram
followers, launched in last 18 months, DTC or 1-2 local retailers, no funding announcements,
founder-led. Exclude: national retail (Whole Foods, Target, Costco...), any priced VC round,
over 50k followers, major press, brands you recognize (e.g. Poppi, Olipop, Liquid Death).
Default rule: when uncertain, exclude.

## Build steps (one Claude Code session each; stop after each)
**Phase 1**
1. Project skeleton: `uv` project, dependencies, `.env` loading in `scout/config.py`,
   a one-page Streamlit app that says "Scout", and instructions to run Phoenix locally.
2. Database + Fund Profile page: `scout/db.py` creates tables; a form to edit and save the
   fund profile, prefilled with the Brand Project template.
3. Web tools: `search_web` and `read_page` in `scout/tools.py`, plus `scripts/try_tools.py`
   to test them from the terminal.
4. Scoring: `scout/scoring.py` scores a company against the rubric with structured output;
   wrapped as the `score_against_thesis` tool.
5. The agent: `scout/agent.py` (LangGraph ReAct agent, system prompt builder, `check_watchlist`
   and `save_candidate` tools) and `scout/tracing.py` (Phoenix). Run it from the terminal and see
   the full trace in Phoenix. **Key milestone.**
6. Source page + Inbox: run the agent from the UI with live progress; review results; thumbs up/down
   with a reason; save to watchlist or pass.
7. Learning: `scout/feedback.py` turns feedback into learned preferences used by the next run.
8. Watchlist dashboard + basic company page.

**Phase 2**
9. `research_founders` tool and a deep company profile page.
10. Evals: `evals/run_evals.py` uses Phoenix evals (LLM-as-judge) to check "is this company
    actually early-stage?" and "are founder facts supported by sources?"; results logged to Phoenix.
11. Fix loop: use eval failures to improve the prompt or tools; re-run and compare.

**Phase 3**
12. Cadence: daily target from the fund profile; scheduled runs while the app is running.
13. Change tracking: re-research watchlist companies and show what changed.
