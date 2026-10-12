# Checks every watchlist company for changes from the terminal (same as the Watchlist button).
# Handy for running on a schedule outside the app later, e.g. from cron.
#   uv run python -m scripts.check_watchlist

from scout import companies, db
from scout.changes import check_company


def main() -> None:
    """Re-research each watched company and print what changed."""
    db.init_db()
    watching = companies.list_companies("watching")
    if not watching:
        print("The watchlist is empty.")
    for company in watching:
        check = check_company(company)
        flag = "  ⚠ EXCLUSION SIGNAL" if check["exclusion_now_applies"] else ""
        print(f"\n{company['name']}: {check['summary']}{flag}")
        for change in check["changes"]:
            print(f"  - {change['field']}: {change['before']} -> {change['after']}")


if __name__ == "__main__":
    main()
