# Scout

An agentic deal-sourcing analyst for VC funds. See `SPEC.md` for the full plan.

## How it's organized

- `app.py`: the entry point and router. Shared setup, the sidebar's "Run agentic analysis" button, page menu.
- `views/`: the pages. Dashboard, Explore (swipe review), Watchlist, Fund Profile, Company.
- `ui/`: UI pieces shared by several pages (swipe card, company detail sections, run dialog).
- `scout/`: the backend, with no UI code. Agent, tools, scoring, founders, feedback learning,
  change tracking, scheduler, and the SQLite database.
- `evals/`: LLM-as-judge evals and the before/after comparison.
- `scripts/`: terminal helpers to try each piece on its own.

## Install

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # then open .env and paste in your ANTHROPIC_API_KEY and TAVILY_API_KEY
```

## Run the app

```bash
uv run streamlit run app.py
```

Then open the URL it prints (usually http://localhost:8501).

## Run Phoenix (tracing), in a second terminal

```bash
uv run phoenix serve
```

Then open http://localhost:6006. Traces will appear here once the agent exists (Build Step 5).

## Run the agent from the terminal

```bash
uv run python -m scripts.run_agent --n 1 --focus "functional beverages"
```

## Run the evals

Checks every saved company with two LLM judges: is it really early-stage, and are its founder
facts backed by sources? Start Phoenix first, then:

```bash
uv run python -m evals.run_evals --label baseline
```

Where to see the results:
- **Phoenix > Datasets & Experiments:** each eval run is an experiment over a dataset of
  your saved companies (one row per company, a column per judge). Open two experiments to
  compare them side by side.
- **Phoenix > Projects > scout:** each verdict is also attached to the trace step where the
  agent saved that company (filter spans with `name == 'save_candidate'`).
- **evals/results/:** a CSV of every run (also written when Phoenix isn't running).

## Compare evals (the fix loop)

Label each eval run, make one change, re-run on the same agent runs, then compare. Evaluating
the same companies reuses the same Phoenix dataset, so the experiments line up side by side
in Phoenix; `evals.compare` shows the same comparison in the terminal.

```bash
uv run python -m evals.run_evals --runs 1 3 --label baseline
uv run python -m evals.run_evals --runs 1 3 --label after-fix
uv run python -m evals.compare
```

## Check watchlist companies for changes

Re-researches every company on the watchlist and records what changed since it was saved
(also available as a button on the Watchlist page and on each Company page).

```bash
uv run python -m scripts.check_watchlist
```
