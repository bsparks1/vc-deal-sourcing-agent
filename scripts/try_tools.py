# A small terminal script to try the web tools by hand, without the agent or the UI.
# Run from the project folder:
#   uv run python -m scripts.try_tools search "functional soda brand launched 2026"
#   uv run python -m scripts.try_tools read https://example.com

import argparse
import json

from scout.tools import read_page, search_web


def main() -> None:
    """Parse the command-line arguments, call one tool, and print its result."""
    parser = argparse.ArgumentParser(description="Try Scout's web tools from the terminal.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    search_cmd = subcommands.add_parser("search", help="Search the web")
    search_cmd.add_argument("query", help="What to search for (put it in quotes)")

    read_cmd = subcommands.add_parser("read", help="Read one web page")
    read_cmd.add_argument("url", help="The page URL")

    args = parser.parse_args()

    # Tools wrapped with @tool are called with .invoke({argument_name: value}),
    # exactly how the agent will call them in Step 5.
    if args.command == "search":
        result = search_web.invoke({"query": args.query})
    else:
        result = read_page.invoke({"url": args.url})

    # indent=2 pretty-prints; ensure_ascii=False keeps characters like é and ™ readable.
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
