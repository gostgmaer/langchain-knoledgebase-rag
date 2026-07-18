from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from packages.config.loader import settings

from .exceptions import ProviderNotSupportedError


class LLMRegistry:

    @staticmethod
    def create():

        provider = settings.llm.provider.lower()

        common = {
            "temperature": settings.llm.temperature,
        }

        if provider == "google":
            return ChatGoogleGenerativeAI(
                model=settings.llm.model,
                google_api_key=settings.google.api_key,
                **common,
            )

        if provider == "openai":
            return ChatOpenAI(
                model=settings.llm.model,
                api_key=settings.openai.api_key,
                **common,
            )

        if provider == "anthropic":
            return ChatAnthropic(
                model=settings.llm.model,
                api_key=settings.anthropic.api_key,
                **common,
            )

        if provider == "groq":
            return ChatGroq(
                model=settings.llm.model,
                api_key=settings.groq.api_key,
                **common,
            )

        raise ProviderNotSupportedError(provider)