class IAMEndpoints:
    """IAM endpoints consumed by the AI Platform."""

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    HEALTH = "/health"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    # Public key set for local RS256 JWT verification.
    JWKS = "/.well-known/jwks.json"

    # Service-to-service authentication.
    TOKEN = "/auth/token"

    # Validate an existing session and retrieve fresh roles/permissions.
    INTROSPECT = "/auth/introspect"

    # Current authenticated user.
    ME = "/auth/me"

    # ------------------------------------------------------------------
    # User
    # ------------------------------------------------------------------

    PROFILE = "/profile"

    USER = "/users/{user_id}"

    USERS = "/users"

    # ------------------------------------------------------------------
    # Tenant
    # ------------------------------------------------------------------

    TENANT = "/tenants/{tenant_id}"