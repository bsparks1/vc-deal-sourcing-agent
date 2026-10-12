# Compares two eval results (CSV files from evals/run_evals.py) to see if a fix helped.
# This is the "re-run and compare" half of the fix loop (Build Step 11):
#   uv run python -m evals.compare                     (the two newest results)
#   uv run python -m evals.compare OLD.csv NEW.csv     (two specific results)

import sys
from pathlib import Path

import pandas as pd

from evals.run_evals import EVALUATORS, RESULTS_DIR


def pick_files(args: list[str]) -> tuple[Path, Path]:
    """Return (older, newer) result files: the two given, or the two newest in evals/results."""
    if len(args) == 2:
        return Path(args[0]), Path(args[1])
    # File names start with a timestamp, so sorting by name sorts by time.
    files = sorted(RESULTS_DIR.glob("evals_*.csv"))
    if len(files) < 2:
        sys.exit("Need at least two eval results in evals/results/ to compare.")
    return files[-2], files[-1]


def summarize(table: pd.DataFrame, name: str) -> tuple[str, str]:
    """Return a one-line average and a label breakdown for one evaluator's columns."""
    scores = table[f"{name}_score"].dropna()  # unscored rows (e.g. no_founders) left out
    average = f"{scores.mean():.2f} (n={len(scores)})" if len(scores) else "n/a"
    counts = table[f"{name}_label"].value_counts().to_dict()
    return average, ", ".join(f"{label}: {count}" for label, count in counts.items())


def main() -> None:
    """Print a before/after comparison, then list what still fails in the newer run."""
    old_path, new_path = pick_files(sys.argv[1:])
    old, new = pd.read_csv(old_path), pd.read_csv(new_path)
    print(f"BEFORE: {old_path.name} ({len(old)} companies)")
    print(f"AFTER:  {new_path.name} ({len(new)} companies)\n")

    for evaluator in EVALUATORS:
        old_avg, old_labels = summarize(old, evaluator.name)
        new_avg, new_labels = summarize(new, evaluator.name)
        print(f"{evaluator.name}\n  average: {old_avg} -> {new_avg}")
        print(f"  before:  {old_labels}\n  after:   {new_labels}\n")

    # Small samples swing a lot by chance, so always read the actual failures, not just averages.
    print("Still failing in AFTER (score below 1):")
    found = False
    for evaluator in EVALUATORS:
        failing = new[new[f"{evaluator.name}_score"] < 1]
        for _, row in failing.iterrows():
            found = True
            print(f"- {row['name']} [{evaluator.name}: {row[f'{evaluator.name}_label']}] "
                  f"{row[f'{evaluator.name}_explanation']}")
    if not found:
        print("- nothing")


if __name__ == "__main__":
    main()
