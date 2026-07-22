class IAMEndpoints:
    """
    IAM endpoints consumed by the AI Platform, called through
    `web-agency-backend-api`'s gateway (`https://gateway.easydev.in`),
    not the IAM service directly. Every path below has the gateway's
    real, live-confirmed prefix baked in — the gateway does NOT use one
    consistent prefix the way calling IAM directly does (everything
    under `/api/v1/iam/*`); it routes by resource group instead:

        /api/auth/*      -> IAM's /api/v1/iam/auth/*
        /api/users/*      -> IAM's /api/v1/iam/users/*
        /api/tenants/*    -> IAM's /api/v1/iam/tenants/*
        /api/rbac/*       -> IAM's /api/v1/iam/rbac/*
        /api/sessions/*   -> IAM's /api/v1/iam/sessions/*
        /api/profile      -> IAM's /api/v1/iam/profile
        /api/iam/*        -> catch-all for everything else (confirmed
                             live: this is where /health lives — NOT
                             /api/health)

    Confirmed live, one at a time, against the real gateway (not
    assumed from the pattern above): HEALTH, TOKEN, REFRESH,
    INTROSPECT, ME, USER's group prefix, TENANT's group prefix, and
    PROFILE. SESSION/USERS/JWKS are unconfirmed — nothing in this SDK
    calls them yet (see each constant's own note).
    """

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    # Confirmed live: /api/health (no /iam/) 404s through the gateway;
    # /api/iam/health is the real one, since /api/iam/* is the
    # catch-all for routes with no resource-specific gateway prefix.
    HEALTH = "/api/iam/health"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    # Public key set for local RS256 JWT verification. Confirmed live:
    # NOT reachable through the gateway under any prefix tried
    # (/api/iam/.well-known/*, /api/auth/.well-known/*, bare
    # /.well-known/*  all 404). JWKS has to be fetched from the IAM
    # service directly (settings.jwks_base_url), not the gateway —
    # unused by any SDK method today, so this is unwired rather than
    # silently wrong.
    JWKS = "/.well-known/jwks.json"

    # Service-to-service authentication. Confirmed live through the
    # gateway: real 401 "Invalid client credentials" with placeholder
    # creds, same message as calling IAM directly.
    TOKEN = "/api/auth/token"

    # Exchange a refresh token for a new access token. Confirmed live
    # through the gateway: real 401, though with a *different* message
    # than IAM returns directly ("Session expired. Please log in
    # again." via the gateway vs. "Invalid refresh token" direct) —
    # the gateway appears to add its own session-handling layer on top
    # of this one specifically, not a transparent proxy for it. Body
    # key is still {"refreshToken": "..."} either way — a
    # "refresh_token" (snake_case) key is rejected outright with a 400
    # ("property refresh_token should not exist").
    REFRESH = "/api/auth/refresh"

    # Unconfirmed — nothing in this SDK calls it yet. Grouped under
    # /api/auth/ on the (unverified) assumption it follows the same
    # pattern as every other confirmed /auth/* route.
    SESSION = "/api/auth/session"

    # Validate an existing session and retrieve fresh roles/permissions.
    # Confirmed live through the gateway: real 401 "Invalid or expired
    # API key" with a placeholder key, same message as calling IAM
    # directly.
    INTROSPECT = "/api/auth/introspect"

    # Current authenticated user. Confirmed live through the gateway:
    # real 401 "Invalid or expired token" with a bad token, same
    # message as calling IAM directly.
    ME = "/api/auth/me"

    # ------------------------------------------------------------------
    # User
    # ------------------------------------------------------------------

    # Confirmed live: real 401 "Access denied. No token provided"
    # through the gateway (not under /api/iam/ or /api/auth/).
    PROFILE = "/api/profile"

    # Unconfirmed for this exact shape — nothing in this SDK calls
    # USERS (plural/list) yet, but the /api/users/* group prefix
    # itself is confirmed live (see USER below).
    USER = "/api/users/{user_id}"

    USERS = "/api/users"

    # ------------------------------------------------------------------
    # Tenant
    # ------------------------------------------------------------------

    # /api/tenants/* group prefix confirmed live (real 401, not 404).
    TENANT = "/api/tenants/{tenant_id}"
