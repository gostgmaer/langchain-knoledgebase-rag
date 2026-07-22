# Knowledge Base Search / Document Search tools
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from langchain.tools import tool
from langgraph.prebuilt import InjectedState

from packages.knowledge.manager import KnowledgeManager
from packages.knowledge.vectorstores.schema import SearchFilter
from packages.shared.logging import get_logger

logger = get_logger(__name__)


def _serialize(results) -> list[dict]:
    return [
        {
            "document_id": str(result.chunk.document_id),
            "chunk_id": str(result.chunk.id),
            "content": result.chunk.content,
            "score": result.score,
        }
        for result in results
    ]


def make_knowledge_base_search_tool(knowledge_manager: KnowledgeManager):
    """
    Builds the `search_knowledge_base` tool bound to a specific (request-scoped)
    KnowledgeManager instance. A factory rather than a module-level @tool
    because KnowledgeManager itself is DI-wired per-request (it depends on
    repositories bound to a per-request database session) — capturing one at
    import time the way calculator/weather do would risk the same
    Singleton-captures-a-stale-session bug class this project has hit before.
    """

    @tool(
        "search_knowledge_base",
        description=(
            "Explicitly search the user's knowledge base for a specific query. "
            "Use this when the user asks you to look something up in their "
            "uploaded documents on demand — separate from the automatic "
            "retrieval that already runs for every message, this lets you "
            "search again mid-conversation with a refined or different query."
        ),
        return_direct=False,
    )
    async def search_knowledge_base(
        query: str,
        state: Annotated[dict, InjectedState],
    ) -> dict:
        try:
            results = await knowledge_manager.search(
                query=query,
                filters=SearchFilter(
                    tenant_id=state["tenant_id"],
                    model_profile_id=state["model_profile_id"],
                ),
            )

            logger.debug("search_knowledge_base tool invoked", query=query, results=len(results))

            return {
                "success": True,
                "tool": "search_knowledge_base",
                "query": query,
                "results": _serialize(results),
            }

        except Exception as exc:
            logger.exception("search_knowledge_base tool failed")
            return {
                "success": False,
                "tool": "search_knowledge_base",
                "error": str(exc),
            }

    return search_knowledge_base


def make_document_search_tool(knowledge_manager: KnowledgeManager):
    """
    Builds the `search_document` tool — same DI-scoping reasoning as
    make_knowledge_base_search_tool above. Scoped to one document rather
    than the whole knowledge base; `document_id` is expected to come from a
    citation the model has already seen earlier in the conversation (there
    is no "list documents" tool yet to discover IDs from scratch).
    """

    @tool(
        "search_document",
        description=(
            "Search within a single, specific document rather than the whole "
            "knowledge base, identified by its document_id (as seen in a "
            "citation earlier in this conversation). Use this for a focused "
            "follow-up question scoped to one document the user has already "
            "been shown a citation for."
        ),
        return_direct=False,
    )
    async def search_document(
        query: str,
        document_id: str,
        state: Annotated[dict, InjectedState],
    ) -> dict:
        try:
            results = await knowledge_manager.search_by_document(
                query=query,
                tenant_id=state["tenant_id"],
                model_profile_id=state["model_profile_id"],
                document_id=UUID(document_id),
            )

            logger.debug("search_document tool invoked", document_id=document_id, results=len(results))

            return {
                "success": True,
                "tool": "search_document",
                "query": query,
                "document_id": document_id,
                "results": _serialize(results),
            }

        except ValueError:
            return {
                "success": False,
                "tool": "search_document",
                "error": f"'{document_id}' is not a valid document_id.",
            }
        except Exception as exc:
            logger.exception("search_document tool failed")
            return {
                "success": False,
                "tool": "search_document",
                "error": str(exc),
            }

    return search_document
