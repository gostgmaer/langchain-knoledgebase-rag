from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.tools import tool

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