# Common auth
from __future__ import annotations

from typing import Protocol


class TokenProvider(Protocol):
    async def get_token(self) -> str: ...


class StaticTokenProvider:
    def __init__(self, token: str) -> None:
        self._token = token

    async def get_token(self) -> str:
        return self._token


class BearerAuth:
    def __init__(
        self,
        token_provider: TokenProvider,
    ) -> None:
        self._provider = token_provider

    async def headers(self) -> dict[str, str]:
        token = await self._provider.get_token()

        return {
            "Authorization": f"Bearer {token}",
        }


class ApiKeyAuth:
    def __init__(
        self,
        api_key: str,
        header: str = "x-api-key",
    ) -> None:
        self._api_key = api_key
        self._header = header

    async def headers(self) -> dict[str, str]:
        return {
            self._header: self._api_key,
        }