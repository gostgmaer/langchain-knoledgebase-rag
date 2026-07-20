# News tool
# ============================================================
# core/tools/news.py — News Tool
# ============================================================
# TODO: Define `get_news(query, category)` tool function
# TODO: Call NewsAPI using NEWS_API_KEY
# TODO: Parse and return top headlines as structured data
# TODO: Handle API errors and empty results
# ============================================================


from langchain_tavily import TavilySearch
from langchain.tools import tool
from packages.logging.logger import get_logger
from packages.config.loader import settings
logger = get_logger(__name__)

@tool(
    "get_news",
    description="Get the latest news for a given topic.",
)
async def get_news(topic: str):
    """Get the latest news for a topic."""

    api_key = settings.tools.tavily_api_key
    if not api_key:
        return "Tavily API key is missing."

    try:
        search = TavilySearch(
            max_results=5,
            api_wrapper={"tavily_api_key": api_key},
        )


        results =  search.invoke({"query": f"Latest news about {topic}"})

        logger.debug("News tool executed for %s", topic)

        return results

    except Exception as e:
        logger.exception("News tool failed")
        return f"Unable to reach the news service: {e}"
