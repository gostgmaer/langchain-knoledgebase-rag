# IAM user/tenant lookup tools — Internal EasyDev API Integration
# (docs/mvpRAG.md v1.1). Wraps the existing packages/sdk/iam/ client,
# not a new service integration.
from __future__ import annotations

from typing import Annotated

from langchain.tools import tool
from langgraph.prebuilt import InjectedState

from packages.sdk.common.exceptions import SDKException
from packages.sdk.iam.client import IAMClient
from packages.shared.logging import get_logger

logger = get_logger(__name__)


def make_iam_user_lookup_tool(iam_client: IAMClient):
    """
    Builds the `lookup_iam_user` tool bound to a specific IAMClient.
    Factory pattern matching packages/tools/builtin/knowledge_base.py
    for consistency — IAMClient itself is `providers.Singleton`
    (stateless, safe to share process-wide, see
    packages/infrastructure/container/iam.py), unlike KnowledgeManager,
    but keeping every DI-backed tool the same shape is worth more than
    the one line saved by making this a bare module-level @tool.

    IAM's own `GET /users/:id` (IAMUsersSDK.get_user(), its only
    method) has no server-side tenant scoping — this tool adds a
    client-side check against the caller's own tenant_id and refuses
    to return data across tenants, but that is NOT a real security
    boundary (enforced here, in app code, not by IAM itself) —
    disclosed honestly rather than implied to be authoritative, the
    same way this app's fail-open IAM auth is already documented.

    No real IAM backend is reachable in this dev environment
    (IAM_BASE_URL refuses connections) — both SDKException (a real
    error response) and any other connection-level failure are caught
    and returned as a clear "unreachable" tool result instead of
    crashing the graph turn, matching AuthService.resolve()'s existing
    fail-open idiom elsewhere in this app.
    """

    @tool(
        "lookup_iam_user",
        description=(
            "Look up an EasyDev platform user's profile (name, email, active "
            "status) by their user_id. Only returns data for users belonging "
            "to the caller's own tenant."
        ),
        return_direct=False,
    )
    async def lookup_iam_user(
        user_id: str,
        state: Annotated[dict, InjectedState],
    ) -> dict:
        try:
            user = await iam_client.users.get_user(user_id)
        except SDKException as exc:
            logger.warning("lookup_iam_user: IAM service returned an error", error=str(exc))
            return {
                "success": False,
                "tool": "lookup_iam_user",
                "error": f"IAM service error: {exc}",
            }
        except Exception as exc:
            logger.warning("lookup_iam_user: IAM service unreachable", error=str(exc))
            return {
                "success": False,
                "tool": "lookup_iam_user",
                "error": "IAM service is currently unreachable.",
            }

        if str(user.tenant_id) != str(state["tenant_id"]):
            return {
                "success": False,
                "tool": "lookup_iam_user",
                "error": "Access denied: that user does not belong to your tenant.",
            }

        return {
            "success": True,
            "tool": "lookup_iam_user",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
            },
        }

    return lookup_iam_user


def make_iam_tenant_lookup_tool(iam_client: IAMClient):
    """
    Builds the `lookup_iam_tenant` tool — always resolves the caller's
    OWN tenant (state["tenant_id"]); there is no LLM-facing tenant_id
    parameter at all, so the model can never look up an arbitrary
    tenant, mirroring how make_knowledge_base_search_tool never
    exposes tenant_id to the LLM either.
    """

    @tool(
        "lookup_iam_tenant",
        description=(
            "Look up details about the current tenant/organization (name, "
            "status) this conversation belongs to. Takes no arguments — "
            "always resolves the caller's own tenant."
        ),
        return_direct=False,
    )
    async def lookup_iam_tenant(
        state: Annotated[dict, InjectedState],
    ) -> dict:
        try:
            tenant = await iam_client.tenants.get_tenant(str(state["tenant_id"]))
        except SDKException as exc:
            logger.warning("lookup_iam_tenant: IAM service returned an error", error=str(exc))
            return {
                "success": False,
                "tool": "lookup_iam_tenant",
                "error": f"IAM service error: {exc}",
            }
        except Exception as exc:
            logger.warning("lookup_iam_tenant: IAM service unreachable", error=str(exc))
            return {
                "success": False,
                "tool": "lookup_iam_tenant",
                "error": "IAM service is currently unreachable.",
            }

        return {
            "success": True,
            "tool": "lookup_iam_tenant",
            "tenant": {
                "id": str(tenant.id),
                "name": tenant.name,
                "slug": tenant.slug,
                "is_active": tenant.is_active,
            },
        }

    return lookup_iam_tenant
