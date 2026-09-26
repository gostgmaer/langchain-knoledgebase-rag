"""
Shared plumbing for the Microsoft 365 connectors (Teams, SharePoint, OneDrive): authentication against
Microsoft Entra ID and paged Microsoft Graph calls. Not a connector itself.

Two ways to authenticate, both stored only in the encrypted credential:
  * app registration (tenant id + client id + client secret): client-credentials flow, token cached until
    shortly before it expires and refreshed on a 401;
  * a pre-issued access token (short-lived; for testing or delegated use, cannot refresh).
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from packages.connectors.base import BaseKnowledgeConnector, ConfigField, ValidationResult
from packages.connectors.http import AuthenticationFailed, ConnectorHttpError, ResilientHttpClient

DEFAULT_AUTHORITY = "https://login.microsoftonline.com"
DEFAULT_GRAPH = "https://graph.microsoft.com/v1.0"


class GraphConnector(BaseKnowledgeConnector):
    credential_kind = "oauth_client"
    supports_permissions = True

    credential_fields = (
        ConfigField("tenant_id", "Directory (tenant) ID", "string", group="connection", help="Entra ID tenant of the app registration."),
        ConfigField("client_id", "Application (client) ID", "string", group="connection"),
        ConfigField("client_secret", "Client secret", "secret", group="connection"),
        ConfigField("access_token", "Access token (instead of the app registration)", "secret", group="connection",
                    help="Short-lived; cannot be refreshed. Prefer the app registration."),
    )
    _graph_fields = (
        ConfigField("graph_base_url", "Graph endpoint", "url", default=DEFAULT_GRAPH, group="advanced", help="Change only for sovereign clouds."),
        ConfigField("authority_host", "Sign-in endpoint", "url", default=DEFAULT_AUTHORITY, group="advanced"),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._token_value: str | None = None
        self._token_expires_at: float = 0.0

    # ------------------------------------------------------------------ setup

    def build_http(self) -> ResilientHttpClient:
        return ResilientHttpClient(
            headers={"Accept": "application/json"},
            min_interval=0.1,
            max_concurrency=4,
            allow_private=self.allow_private,
        )

    async def validate_credentials(self) -> ValidationResult:
        # Either form is acceptable: an app registration, or a pre-issued access token.
        cred = self.credentials
        has_app = all(cred.get(k) for k in ("tenant_id", "client_id", "client_secret"))
        if not (cred.get("access_token") or has_app):
            return ValidationResult(ok=False, errors=["Provide the tenant id, client id and client secret, or an access token."])
        return ValidationResult(ok=True)

    @property
    def _graph(self) -> str:
        return str(self.configuration.get("graph_base_url") or DEFAULT_GRAPH).rstrip("/")

    # ------------------------------------------------------------------ auth

    async def _token(self, *, force: bool = False) -> str:
        static = self.credentials.get("access_token")
        if static:
            return str(static)
        if not force and self._token_value and time.monotonic() < self._token_expires_at - 60:
            return self._token_value
        authority = str(self.configuration.get("authority_host") or DEFAULT_AUTHORITY).rstrip("/")
        response = await self.http.request(
            "POST",
            f"{authority}/{self.credentials['tenant_id']}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.credentials["client_id"],
                "client_secret": self.credentials["client_secret"],
                "scope": f"{self._graph.split('/v1.0')[0]}/.default",
            },
            raise_auth_errors=False,  # read the error code from the body instead
        )
        if response.status_code >= 400:
            try:
                code = response.json().get("error", "unknown_error")
            except ValueError:
                code = "unknown_error"
            raise AuthenticationFailed(f"Microsoft sign-in failed ({code}). Check the tenant, client id and secret.", status=response.status_code)
        body = response.json()
        self._token_value = body["access_token"]
        self._token_expires_at = time.monotonic() + float(body.get("expires_in", 3600))
        return self._token_value

    def auth_headers_for(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    # ------------------------------------------------------------------ Graph calls

    async def graph_get(self, path_or_url: str, **params: Any) -> dict[str, Any]:
        url = path_or_url if path_or_url.startswith("http") else f"{self._graph}{path_or_url}"
        for attempt in (0, 1):
            token = await self._token(force=attempt == 1)
            try:
                response = await self.http.get(url, params=params or None, headers=self.auth_headers_for(token))
            except AuthenticationFailed:
                if attempt == 0 and not self.credentials.get("access_token"):
                    continue  # the cached token may have been revoked/expired: sign in again once
                raise
            if response.status_code == 404:
                raise ConnectorHttpError("Not found in Microsoft Graph.", status=404)
            if response.status_code >= 400:
                raise ConnectorHttpError(f"Microsoft Graph returned HTTP {response.status_code}.", status=response.status_code)
            return response.json()
        raise AuthenticationFailed("Microsoft Graph rejected the credentials.")

    async def graph_paged(self, path: str, **params: Any) -> AsyncIterator[dict[str, Any]]:
        next_url: str | None = None
        first = True
        while first or next_url:
            data = await (self.graph_get(next_url) if next_url else self.graph_get(path, **params))
            first = False
            for item in data.get("value", []):
                yield item
            next_url = data.get("@odata.nextLink")

    async def graph_bytes(self, path_or_url: str) -> bytes:
        url = path_or_url if path_or_url.startswith("http") else f"{self._graph}{path_or_url}"
        token = await self._token()
        # The credential is sent to Graph only; the redirect to the pre-signed download host drops it.
        response = await self.http.get(url, headers=self.auth_headers_for(token))
        if response.status_code >= 400:
            raise ConnectorHttpError(f"Download failed (HTTP {response.status_code}).", status=response.status_code)
        return response.content

    async def test_connection(self) -> Any:  # concrete connectors extend this
        from packages.connectors.models import ConnectionTestResult

        try:
            await self._token()
            data = await self.graph_get("/organization", **{"$select": "displayName"})
        except AuthenticationFailed as exc:
            return ConnectionTestResult(False, str(exc), authenticated=False)
        except ConnectorHttpError as exc:
            # A token that works but cannot read /organization still proves authentication.
            return ConnectionTestResult(exc.status in (403,), f"Authenticated, but Graph refused a basic read: {exc}", authenticated=True)
        org = (data.get("value") or [{}])[0].get("displayName")
        return ConnectionTestResult(True, f"Connected to Microsoft 365{f' ({org})' if org else ''}.", authenticated=True)
