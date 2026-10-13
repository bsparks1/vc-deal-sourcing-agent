# Runs the evals as a Phoenix "experiment", so the results show up in Phoenix under
# Datasets & Experiments: a table with one row per company and a column per judge, and a
# side-by-side comparison between eval runs (e.g. "baseline" vs "after-fix").
# The saved companies become a Phoenix dataset; each eval run is one experiment over it.

import pandas as pd
from phoenix.client import Client
from phoenix.evals import bind_evaluator

from evals.judges import early_stage, founders_supported
from scout import config

# Fields copied into each dataset example (the company as the agent saved it).
INPUT_FIELDS = ["id", "name", "domain", "stage", "funding", "traction", "sources", "founders"]


def dataset_name(run_ids: list[int] | None) -> str:
    """Same companies -> same dataset, so their experiments can be compared side by side."""
    if run_ids:
        return "scout-runs-" + "-".join(str(r) for r in sorted(run_ids))
    return "scout-all-companies"


def upsert_dataset(client: Client, name: str, data: pd.DataFrame):
    """Get the dataset, adding any companies it doesn't have yet (or create it).

    Datasets only grow: a company already in it keeps its example, so earlier experiments
    stay comparable. Each example links to the trace step that saved the company.
    """
    try:
        dataset = client.datasets.get_dataset(dataset=name)
        known = {example["metadata"].get("company_id") for example in dataset.examples}
    except ValueError:  # the client raises ValueError when the dataset doesn't exist yet
        dataset, known = None, set()

    new = data[~data["id"].isin(known)]
    if new.empty:
        return dataset
    # Built as plain dicts (not a pandas table) so lists like sources and founders stay lists;
    # Phoenix turns lists in a table into text. A company saved while Phoenix was off has no
    # trace step to link to, so its span_id is None.
    examples = [{
        "input": {field: row[field] for field in INPUT_FIELDS},
        "output": {},
        "metadata": {"company_id": int(row["id"])},
        "span_id": row["span_id"] if isinstance(row["span_id"], str) else None,
    } for row in new.to_dict("records")]
    if dataset is None:
        return client.datasets.create_dataset(
            name=name, examples=examples, dataset_description="Companies saved by Scout's agent")
    return client.datasets.add_examples_to_dataset(dataset=name, examples=examples)


def run_as_experiment(data: pd.DataFrame, run_ids: list[int] | None, label: str):
    """Evaluate the companies as a Phoenix experiment.

    Returns (results table, experiment URL). The table has the same columns as the CSV:
    id, name, domain, and label/score/explanation for each judge.
    """
    client = Client(base_url=config.PHOENIX_ENDPOINT)
    dataset = upsert_dataset(client, dataset_name(run_ids), data)

    # Nothing is re-run: the "task" just hands each saved company to the judges.
    def task(input):
        return input

    # The judges expect fields like `name` and `founders`; in an experiment they arrive
    # inside the example's "input", so map each field to where it really is. Each mapping
    # takes exactly one argument, so Phoenix passes it the whole example.
    def field_from_input(field):
        return lambda example: example["input"][field]

    def from_input(*fields):
        return {field: field_from_input(field) for field in fields}

    judges = [
        bind_evaluator(early_stage, from_input("name", "domain", "stage", "funding",
                                               "traction", "sources")),
        bind_evaluator(founders_supported, from_input("name", "founders")),
    ]
    ran = client.experiments.run_experiment(
        dataset=dataset, task=task, evaluators=judges, print_summary=False,
        experiment_name=label or "eval", experiment_description="Scout LLM-as-judge evals",
    )

    # Turn the experiment's results back into one row per company.
    company_by_run = {run["id"]: run["output"] for run in ran["task_runs"]}
    rows = {}
    for evaluation in ran["evaluation_runs"]:
        company = company_by_run[evaluation.experiment_run_id]
        # Values come back from Phoenix as JSON, so make sure the id is a number again.
        row = rows.setdefault(int(company["id"]), {"id": int(company["id"]), "name": company["name"],
                                                    "domain": company["domain"]})
        result = evaluation.result or {}
        for field in ("label", "score", "explanation"):
            row[f"{evaluation.name}_{field}"] = result.get(field)
        if evaluation.error:
            row[f"{evaluation.name}_explanation"] = f"Evaluator failed: {evaluation.error}"
    url = client.experiments.get_experiment_url(dataset_id=ran["dataset_id"],
                                                experiment_id=ran["experiment_id"])
    return pd.DataFrame(rows.values()), url
