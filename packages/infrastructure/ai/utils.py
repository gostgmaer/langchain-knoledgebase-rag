from typing import Any


def extract_usage(response: Any) -> dict[str, Any]:
    """
    Normalize token usage across providers.
    """

    if hasattr(response, "usage_metadata"):
        return response.usage_metadata

    if hasattr(response, "response_metadata"):
        return response.response_metadata.get("token_usage", {})

    return {}