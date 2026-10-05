"""
Real execution for DB-backed CUSTOM-category tool definitions (packages/domain/models/tool.py,
docs/BUGS.md item 29) — before this, a `Tool` row was pure metadata with no link to packages/tools/
(the in-process registry that actually powers chat tool-calling). A CUSTOM tool with a
`configuration.url` now becomes a real, callable LangChain tool: the LLM's single text input is
sent to that URL, reusing the same SSRF-safe, retrying, circuit-broken HTTP client every connector
already uses (packages/connectors/http.py) rather than a second, weaker one.

Only CUSTOM is wired this way. The other categories (SEARCH, DATABASE, API, FILE, EMAIL,
NOTIFICATION, AI, UTILITY) already have real, code-defined implementations in packages/tools/
builtin/ with fixed behavior that has nothing to do with a per-row `configuration` dict — a DB row
in one of those categories stays descriptive metadata only, same as before. A generic per-category
execution engine for all of them is a separate, much larger product decision this pass doesn't make.
"""

from __future__ import annotations

from uuid import UUID

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from packages.config.loader import settings
from packages.connectors.http import BlockedUrlError, ConnectorHttpError, ResilientHttpClient
from packages.domain.enums.tool_category import ToolCategory
from packages.domain.models.tool import Tool
from packages.infrastructure.repositories.tool import ToolRepository
from packages.shared.logging import get_logger

logger = get_logger(__name__)

MAX_RESPONSE_CHARS = 4000


class WebhookToolInput(BaseModel):
    input: str = Field(description="The text input to send to this tool.")


def make_webhook_tool(tool: Tool) -> StructuredTool:
    """
    Builds a callable LangChain tool from one CUSTOM-category Tool row.

    `tool.configuration` conventions:
      url (required): the endpoint to call.
      method (optional, default "POST"): "GET" sends `input` as a `?input=` query param;
        anything else POSTs it as a JSON body `{"input": ...}`.
      headers (optional): a flat string->string dict sent with every call.

    Raises ValueError if `configuration.url` is missing — callers should skip registering a
    misconfigured tool rather than let a broken definition reach the LLM.
    """
    url = tool.configuration.get("url")
    if not isinstance(url, str) or not url:
        raise ValueError(f"Tool '{tool.name}' (CUSTOM) has no configuration.url to call.")

    method = str(tool.configuration.get("method", "POST")).upper()
    headers = tool.configuration.get("headers")
    headers = headers if isinstance(headers, dict) else {}
    timeout = float(tool.timeout_seconds)
    max_retries = min(tool.retry_count, 5)

    async def _run(input: str) -> str:
        client = ResilientHttpClient(
            headers=headers,
            timeout=timeout,
            max_retries=max_retries,
            allow_private=settings.rag.connector_allow_private_hosts,
        )
        try:
            if method == "GET":
                response = await client.request(method, url, params={"input": input})
            else:
                response = await client.request(method, url, json={"input": input})
            text = response.text
        except (BlockedUrlError, ConnectorHttpError) as exc:
            logger.warning("Webhook tool call failed", tool=tool.slug, error=str(exc))
            return f"Tool '{tool.name}' call failed: {exc}"
        finally:
            await client.aclose()
        return text[:MAX_RESPONSE_CHARS]

    return StructuredTool.from_function(
        coroutine=_run,
        name=tool.slug,
        description=tool.description or f"Calls the external '{tool.name}' tool.",
        args_schema=WebhookToolInput,
    )


async def load_custom_tools(tool_repository: ToolRepository, tenant_id: UUID) -> list[StructuredTool]:
    """
    Fetches the tenant's active CUSTOM-category tools and builds a real, callable tool for each —
    the one piece of this feature that genuinely needs the DB, done up front by the caller (the
    chat router) so `init_tool_manager` can stay synchronous (see packages/tools/context.py).
    A single misconfigured row is skipped and logged, not allowed to break every other tool.
    """
    rows = await tool_repository.list_by_tenant(tenant_id, limit=200)
    tools: list[StructuredTool] = []
    for row in rows:
        if row.category != ToolCategory.CUSTOM or not row.is_active:
            continue
        try:
            tools.append(make_webhook_tool(row))
        except ValueError as exc:
            logger.warning("Skipping misconfigured custom tool", tool=row.slug, error=str(exc))
    return tools
