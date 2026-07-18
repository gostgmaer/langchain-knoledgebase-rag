# Tools registry
from langchain_core.tools import BaseTool

from .calculator import calculator_tool
from .datetime import datetime_tool
from .news import news_tool
from .weather import weather_tool
from .web_search import web_search_tool


class ToolRegistry:

    @staticmethod
    def get_tools() -> list[BaseTool]:
        return [
            weather_tool,
            news_tool,
            web_search_tool,
            calculator_tool,
            datetime_tool,
        ]