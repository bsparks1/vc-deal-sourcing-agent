# A terminal script to try the scorer by hand, without the agent or the UI.
# Run from the project folder:
#   uv run python -m scripts.try_scoring                      (scores two built-in examples)
#   uv run python -m scripts.try_scoring "facts about a company..."

import json
import sys

from scout import db
from scout.tools import score_against_thesis

# Two hand-written test cases: one clearly established brand (the v1 failure case) and
# one made-up, very early brand. A good scorer should rank the second far above the first.
EXAMPLES = {
    "Established (should score low)": (
        "Name: Poppi. Prebiotic soda. Sold nationally at Target, Walmart, Costco and Whole "
        "Foods. Over 1M Instagram followers. Raised priced VC rounds and was acquired by "
        "PepsiCo. Source: https://en.wikipedia.org/wiki/Poppi_(drink)"
    ),
    "Early (made-up example, should score high)": (
        "Name: Fernwood Tonics (fictional test company). Adaptogenic sparkling tonic. "
        "Launched DTC in March 2026, also sold in two local co-op grocers in Portland. "
        "About 3,200 Instagram followers. No funding announcements found. Founded by a "
        "former herbalist and a beverage R&D lead from a regional kombucha brewer. "
        "Source: https://example.com/fernwood (fictional)"
    ),
}


def main() -> None:
    """Score the company facts given on the command line, or the built-in examples."""
    db.init_db()  # the tool reads the fund profile, so make sure the table exists
    cases = {"Your company": sys.argv[1]} if len(sys.argv) > 1 else EXAMPLES

    for label, facts in cases.items():
        print(f"\n=== {label} ===")
        result = score_against_thesis.invoke({"company_facts": facts})
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
