from __future__ import annotations

from typing import Any

import httpx

from packages.sdk.common.auth import ApiKeyAuth, BearerAuth

from .exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    RateLimitException,
    SDKException,
    ServerException,
    UnauthorizedException,
)


class BaseClient:
    """Base HTTP client for all EasyDev SDKs."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        auth: BearerAuth | ApiKeyAuth | None = None,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._auth = auth

    def _url(self, path: str) -> str:
        """Build an absolute URL."""
        return f"{self._base_url}/{path.lstrip('/')}"

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute an HTTP request."""

        # Extract headers supplied by the caller
        headers = kwargs.pop("headers", None)

        request_headers: dict[str, str] = {}

        # Default authentication headers
        if self._auth:
            request_headers.update(await self._auth.headers())

        # Request-specific headers override defaults
        if headers:
            request_headers.update(headers)

        response = await self._client.request(
            method=method,
            url=self._url(path),
            headers=request_headers,
            **kwargs,
        )

        self._raise_for_status(response)

        return response

    async def _get(
        self,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self._request("GET", path, **kwargs)

    async def _post(
        self,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self._request("POST", path, **kwargs)

    async def _put(
        self,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self._request("PUT", path, **kwargs)

    async def _patch(
        self,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self._request("PATCH", path, **kwargs)

    async def _delete(
        self,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self._request("DELETE", path, **kwargs)

    def _raise_for_status(
        self,
        response: httpx.Response,
    ) -> None:
        """Map HTTP status codes to SDK exceptions."""

        if response.is_success:
            return

        message = self._extract_error_message(response)

        match response.status_code:
            case 400:
                raise BadRequestException(message)
            case 401:
                raise UnauthorizedException(message)
            case 403:
                raise ForbiddenException(message)
            case 404:
                raise NotFoundException(message)
            case 409:
                raise ConflictException(message)
            case 429:
                raise RateLimitException(message)
            case status if status >= 500:
                raise ServerException(message)
            case _:
                raise SDKException(message)

    @staticmethod
    def _extract_error_message(
        response: httpx.Response,
    ) -> str:
        """Extract a meaningful error message."""

        try:
            data = response.json()

            if isinstance(data, dict):
                return (
                    data.get("message")
                    or data.get("detail")
                    or data.get("error")
                    or response.text
                )
        except Exception:
            pass

        return response.text or "Unknown error"