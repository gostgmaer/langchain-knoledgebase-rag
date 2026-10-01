"""
The permission-code taxonomy `require_permission()` (packages/api/dependencies.py) needs to be
anything other than dead code — docs/BUGS.md item 11: the mechanism was fully built and correct,
but attached to zero routes, because inventing the codes is a real product/security decision that
was deliberately not made silently while fixing something else.

Scope and intent, read this before attaching a new code to a route:

- One `<resource>:read` / `<resource>:write` / `<resource>:delete` per router, matching the
  resource each router already represents (its URL prefix) — not one code per endpoint. A handful
  of resources get an extra, narrower code where the *risk* of one specific action is genuinely
  different from the rest of that resource's writes (`KNOWLEDGE_SOURCES_CREDENTIALS`,
  `OBSERVABILITY_PURGE`) — see each resource's own comment below for why.
- Every code here is additive on top of the existing `require_admin()` guard already enforced on
  these routes, not a replacement for it. `require_admin()` stays the unconditional baseline
  (any `ADMIN_ROLES` role, active whenever `AUTH_REQUIRED` is on); `require_permission()` is a
  second, finer check that only has any effect once `ENABLE_RBAC` is turned on (see its own
  docstring) — so a future role like "read-only operator" can be scoped to just `*_read` codes,
  without weakening what every admin can already do today while the flag stays off.
  `Depends(require_admin())` dependencies are left exactly as they already were; this module only
  adds new `Depends(require_permission(...))` dependencies alongside them.
- Nobody's real IAM-issued JWT carries any of these codes yet (`docs/BUGS.md` item 11's own
  original note: "real IAM credentials to verify enforcement against... [don't] exist yet"). Wiring
  these in is inert today (`ENABLE_RBAC` defaults `false`) and stays inert in any real environment
  until both that flag is turned on *and* a role→code mapping is configured on the IAM side —
  turning the flag on before that mapping exists would lock every admin out of these routes, not
  just the ones a taxonomy update is meant to narrow. Flip `ENABLE_RBAC` on deliberately, not as a
  side effect of deploying this file.
- `feature_flags` is deliberately NOT given any permission codes — see that router's own comment
  (`packages/api/routers/feature_flags.py`) for why: it manages the `enable_rbac` flag itself, and
  gating its own routes on a `require_permission()` check (which is itself gated by that same flag)
  would risk locking an admin out of ever turning `enable_rbac` back off once it's on. That router
  keeps `require_admin()` as its only guard, unconditionally.
- `feedback`'s submit route (`POST /feedback`) is intentionally open to any authenticated user
  today (anyone can rate an answer) — only the admin-only review route (`GET /feedback`) gets a
  code. Giving the submit route a permission code would be inventing a new restriction on an
  already-working, deliberately-open endpoint, not describing an existing one.
"""

from __future__ import annotations


class Permission:
    # Agents — packages/api/routers/agents.py
    AGENTS_READ = "agents:read"
    AGENTS_WRITE = "agents:write"

    # Analytics — packages/api/routers/analytics.py (read-only resource, no write/delete routes)
    ANALYTICS_READ = "analytics:read"

    # Documents — packages/api/routers/documents.py
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_WRITE = "documents:write"
    """Upload, re-index, and metadata/access-level changes."""
    DOCUMENTS_DELETE = "documents:delete"

    # Feedback — packages/api/routers/feedback.py. Only the admin review route (GET); submitting
    # feedback (POST) stays open to any authenticated user, see the module docstring above.
    FEEDBACK_READ = "feedback:read"

    # Knowledge Bases — packages/api/routers/knowledge_bases.py
    KNOWLEDGE_BASES_READ = "knowledge_bases:read"
    KNOWLEDGE_BASES_WRITE = "knowledge_bases:write"
    KNOWLEDGE_BASES_DELETE = "knowledge_bases:delete"

    # Knowledge Sources — packages/api/routers/knowledge_sources.py. By far the largest router
    # (connector config, sync control, external identity mappings); `*_WRITE` covers create/edit/
    # sync-control/identity-mapping routes, not just the plain `PATCH` route, since pause/resume/
    # sync/retry are all "operate this already-created source" actions at the same risk level as
    # editing its config — a separate code per sync verb would be taxonomy sprawl for no real
    # security benefit. Credentials get their own code: rotating/revoking a connector's real
    # external secret is a meaningfully higher-risk action than an ordinary config edit.
    KNOWLEDGE_SOURCES_READ = "knowledge_sources:read"
    KNOWLEDGE_SOURCES_WRITE = "knowledge_sources:write"
    KNOWLEDGE_SOURCES_DELETE = "knowledge_sources:delete"
    KNOWLEDGE_SOURCES_CREDENTIALS = "knowledge_sources:credentials"

    # Model Profiles — packages/api/routers/models.py
    MODELS_READ = "models:read"
    MODELS_WRITE = "models:write"

    # Observability — packages/api/routers/observability.py. `*_READ` covers the router-level
    # summary/document-health/audit-log routes. The retention-purge route gets its own code, on
    # top of its existing, separate `require_super_admin()` (not just `require_admin()`) — it
    # deletes rows platform-wide, across every tenant, not just the caller's.
    OBSERVABILITY_READ = "observability:read"
    OBSERVABILITY_PURGE = "observability:purge"

    # Prompts — packages/api/routers/prompts.py
    PROMPTS_READ = "prompts:read"
    PROMPTS_WRITE = "prompts:write"

    # Retrieval Logs — packages/api/routers/retrieval_logs.py (read-only resource)
    RETRIEVAL_LOGS_READ = "retrieval_logs:read"

    # Retrieval Settings — packages/api/routers/retrieval_settings.py
    RETRIEVAL_SETTINGS_READ = "retrieval_settings:read"
    RETRIEVAL_SETTINGS_WRITE = "retrieval_settings:write"

    # Tool Definitions — packages/api/routers/tools.py
    TOOLS_READ = "tools:read"
    TOOLS_WRITE = "tools:write"

    # Upload Jobs — packages/api/routers/upload_jobs.py (read-only resource)
    UPLOAD_JOBS_READ = "upload_jobs:read"

    # Usage — packages/api/routers/usage.py (read-only resource)
    USAGE_READ = "usage:read"
