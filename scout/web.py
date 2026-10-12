# Creates the Tavily client used for web search and page reading.
# Lives in its own small file because two modules need it (scout/tools.py and
# scout/founders.py), and tools.py also imports founders.py; putting it here avoids a
# circular import (two files importing each other).

from tavily import TavilyClient

from scout import config


def get_tavily_client() -> TavilyClient:
    """Create a Tavily client, or stop with a clear error if TAVILY_API_KEY is missing.

    Created inside a function (not at import time) so the app can still start and show
    the missing-key warning when the key isn't set.
    """
    if not config.TAVILY_API_KEY:
        raise RuntimeError("Missing required key: TAVILY_API_KEY. Add it to your .env file.")
    return TavilyClient(api_key=config.TAVILY_API_KEY)
