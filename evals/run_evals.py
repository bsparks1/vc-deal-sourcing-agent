# Runs the two LLM-as-judge evals (evals/judges.py) on every company the agent has saved,
# prints a report, saves the results to evals/results/ (to compare runs over time in Step 11),
# and logs each result to Phoenix on the save_candidate span where the agent saved that company.
#   uv run python -m evals.run_evals                       (all companies)
#   uv run python -m evals.run_evals --limit 3             (just the 3 newest: quick and cheap)
#   uv run python -m evals.run_evals --runs 4 5 --label after-fix  (only those agent runs)

import argparse
import json
from datetime import datetime

import pandas as pd
from phoenix.client import Client
from phoenix.client.types.spans import SpanQuery
from phoenix.evals import evaluate_dataframe

from evals.judges import early_stage, founders_supported
from scout import companies, config, db
from scout.tracing import phoenix_is_running

EVALUATORS = [early_stage, founders_supported]
RESULTS_DIR = config.PROJECT_DIR / "evals" / "results"


def load_companies(limit: int | None, run_ids: list[int] | None) -> pd.DataFrame:
    """Load saved companies (every status) into a table with the columns the judges need.

    run_ids limits it to companies from those agent runs, e.g. the runs made after a fix.
    """
    rows = [c for status in ("new", "watching", "passed") for c in companies.list_companies(status)]
    if run_ids:
        rows = [c for c in rows if c["run_id"] in run_ids]
    rows.sort(key=lambda c: c["id"], reverse=True)  # newest first
    rows = rows[:limit] if limit else rows
    return pd.DataFrame([{
        "id": c["id"], "name": c["name"], "domain": c["domain"],
        "stage": c["stage"] or "unknown", "funding": c["funding_summary"] or "unknown",
        "traction": "; ".join(c["traction"] or []) or "none recorded",
        "sources": c["sources"] or [], "founders": c["founders"] or [],
    } for c in rows])


def flatten(results: pd.DataFrame) -> pd.DataFrame:
    """Turn each evaluator's result dict into plain label / score / explanation columns."""
    table = results[["id", "name", "domain"]].copy()
    for evaluator in EVALUATORS:
        # Each cell is a dict like {"label": ..., "score": ..., "explanation": ...},
        # or empty if that evaluator crashed on this row.
        cells = results[f"{evaluator.name}_score"].apply(lambda cell: cell or {})
        for field in ("label", "score", "explanation"):
            table[f"{evaluator.name}_{field}"] = cells.apply(lambda cell: cell.get(field))
    return table


def save_span_ids(table: pd.DataFrame) -> pd.DataFrame:
    """Find the Phoenix span where the agent saved each company (matched by domain)."""
    # Ask Phoenix for only the save_candidate spans. Downloading every span and filtering
    # here timed out once the project had a few hundred spans.
    saves = Client(base_url=config.PHOENIX_ENDPOINT).spans.get_spans_dataframe(
        query=SpanQuery().where("name == 'save_candidate'"),
        project_identifier=config.PHOENIX_PROJECT, timeout=60,
    ).sort_values("start_time")
    span_by_domain = {}
    for span_id, row in saves.iterrows():  # the index is the span id
        try:
            domain = json.loads(row["attributes.input.value"])["domain"]
        except (TypeError, ValueError, KeyError):
            continue
        span_by_domain[companies.normalize_domain(domain)] = span_id  # later saves win
    table["span_id"] = table["domain"].map(span_by_domain)
    return table


def log_to_phoenix(table: pd.DataFrame) -> int:
    """Attach each eval result to its save_candidate span in Phoenix. Returns how many rows matched."""
    linked = table.dropna(subset=["span_id"])
    client = Client(base_url=config.PHOENIX_ENDPOINT)
    for evaluator in EVALUATORS:
        annotations = pd.DataFrame({
            "span_id": linked["span_id"],
            "label": linked[f"{evaluator.name}_label"],
            "score": linked[f"{evaluator.name}_score"],
            "explanation": linked[f"{evaluator.name}_explanation"],
        # Skip rows with no score: the evaluator failed, or there was nothing to check
        # (e.g. "no_founders"). An empty score would also be NaN, which JSON can't encode.
        }).dropna(subset=["score"])
        if not annotations.empty:
            client.spans.log_span_annotations_dataframe(
                dataframe=annotations, annotation_name=evaluator.name, annotator_kind="LLM")
    return len(linked)


def main() -> None:
    """Run the evals, then report, save, and log the results."""
    parser = argparse.ArgumentParser(description="Evaluate the companies Scout has saved.")
    parser.add_argument("--limit", type=int, default=None, help="Only the N newest companies")
    parser.add_argument("--runs", type=int, nargs="+", help="Only companies from these run ids")
    parser.add_argument("--label", default="", help='Name for this eval, e.g. "baseline"')
    args = parser.parse_args()

    config.require_keys()
    db.init_db()
    data = load_companies(args.limit, args.runs)
    if data.empty:
        print("No saved companies to evaluate yet. Run the agent first.")
        return

    print(f"Evaluating {len(data)} companies (2 judges each; about 20-40s per company)...")
    table = flatten(evaluate_dataframe(data, EVALUATORS, hide_tqdm_bar=False))

    print()
    for _, row in table.iterrows():
        print(f"{row['name']}\n  early_stage: {row['early_stage_label']} - {row['early_stage_explanation']}"
              f"\n  founders:    {row['founders_supported_label']} - {row['founders_supported_explanation']}\n")
    for evaluator in EVALUATORS:
        scores = table[f"{evaluator.name}_score"].dropna()  # leave out "no_founders" etc.
        if len(scores):
            print(f"{evaluator.name}: average {scores.mean():.2f} over {len(scores)} companies")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    # The label goes in the file name so evals.compare can show "baseline -> after-fix".
    suffix = f"_{args.label}" if args.label else ""
    path = RESULTS_DIR / f"evals_{datetime.now():%Y-%m-%d_%H%M%S}{suffix}.csv"
    table.to_csv(path, index=False)
    print(f"\nSaved results to {path.relative_to(config.PROJECT_DIR)}")

    if phoenix_is_running():
        try:
            linked = log_to_phoenix(save_span_ids(table))
            print(f"Logged to Phoenix on {linked} of {len(table)} companies "
                  "(the rest were saved while Phoenix wasn't running).")
        except Exception as error:  # the results are already saved in the CSV
            print(f"Couldn't log to Phoenix ({error}); the CSV has the results.")
    else:
        print("Phoenix isn't running, so results weren't logged there (the CSV has them).")


if __name__ == "__main__":
    main()
