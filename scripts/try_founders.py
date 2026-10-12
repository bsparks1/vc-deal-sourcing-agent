# A terminal script to try founder research by hand, without the agent or the UI.
# Run from the project folder:
#   uv run python -m scripts.try_founders "Good Kynd" goodkynd.com

import json
import sys

from scout.founders import research_founders


def main() -> None:
    """Research the founders of the company named on the command line and print the result."""
    if len(sys.argv) != 3:
        print('Usage: uv run python -m scripts.try_founders "Company Name" domain.com')
        sys.exit(1)
    result = research_founders(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
