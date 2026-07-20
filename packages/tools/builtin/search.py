# Search tool
# ============================================================
# core/tools/search.py — Web Search Tool
# ============================================================
# TODO: Define `web_search(query, num_results)` tool function
# TODO: Support DuckDuckGo, SerpAPI, and Tavily backends
# TODO: Return ranked list of (title, url, snippet) tuples
# TODO: Handle provider selection from SEARCH_PROVIDER env
# ============================================================


import os
from dotenv import load_dotenv
load_dotenv()
from langchain_core.tools import tool
from langchain_community.utilities import GoogleSerperAPIWrapper
from packages.config.loader import settings

@tool(
    "get_google_search",
    description="Get the latest news for a given topic.",
    return_direct=False,
)
def get_google_search(topic: str) -> dict:
    """
    Search Google for the given topic and return live search results.

    Args:
        topic: The search query or topic.

    Returns:
        Structured Google search results.
    """
    
    search = GoogleSerperAPIWrapper(
        serper_api_key=settings.tools.serper_api_key
    )
    return search.results(query=topic,)