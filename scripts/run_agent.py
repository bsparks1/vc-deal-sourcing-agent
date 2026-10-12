# Runs the Scout agent from the terminal and prints each step as it happens.
# Start Phoenix first (`uv run phoenix serve`) to see the full trace at localhost:6006.
#   uv run python -m scripts.run_agent
#   uv run python -m scripts.run_agent --n 2 --focus "functional beverages"

import argparse

from scout.agent import run_agent


def main() -> None:
    """Parse the options, run the agent once, and print the outcome."""
    parser = argparse.ArgumentParser(description="Run the Scout agent once.")
    # Default of 1 keeps test runs quick and cheap; each company takes many tool calls.
    parser.add_argument("--n", type=int, default=1, help="How many companies to find")
    parser.add_argument("--focus", default="", help='Optional focus, e.g. "functional beverages"')
    args = parser.parse_args()

    result = run_agent(target=args.n, focus=args.focus)

    print(f"\nRun {result['run_id']}: {result['status']}, "
          f"{result['companies_saved']} saved")
    if result["error"]:
        print(f"Error: {result['error']}")
    print(f"\n{result['summary']}")
    print("\nSee every step in Phoenix: http://localhost:6006 (project 'scout')")


if __name__ == "__main__":
    main()
