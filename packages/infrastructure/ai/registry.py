from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from packages.config.loader import settings

from .exceptions import ProviderNotSupportedError


class LLMRegistry:

    @staticmethod
    def create():

        provider = settings.ai.default_provider.lower()

        common = {
            "temperature": settings.ai.default_temperature,
        }

        if provider == "google":
            return ChatGoogleGenerativeAI(
                model=settings.ai.model,
                google_api_key=settings.ai.google_api_key,
                **common,
            )

        if provider == "openai":
            return ChatOpenAI(
                model=settings.ai.model,
                api_key=settings.ai.openai_api_key,
                **common,
            )

        if provider == "anthropic":
            return ChatAnthropic(
                model=settings.ai.model,
                api_key=settings.ai.anthropic_api_key,
                **common,
            )

        if provider == "groq":
            return ChatGroq(
                model=settings.ai.model,
                api_key=settings.ai.groq_api_key,
                **common,
            )

        raise ProviderNotSupportedError(provider)