from pydantic_settings import BaseSettings, SettingsConfigDict


class IAMSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IAM_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # The gateway's base host (e.g. https://gateway.easydev.in), not
    # the IAM service directly. packages/sdk/iam/endpoints.py's
    # constants already bake in each route group's real, live-confirmed
    # gateway prefix (/api/auth/*, /api/users/*, /api/tenants/*,
    # /api/iam/* as the catch-all) — this is just the host they're
    # relative to.
    base_url: str

    # JWKS is NOT reachable through the gateway under any prefix
    # (confirmed live — see packages/sdk/iam/endpoints.py's JWKS
    # constant). Only needed if something ever verifies RS256 JWTs
    # locally instead of via /auth/me; unused today, so this has no
    # default and callers must set it themselves if that changes.
    jwks_base_url: str | None = None

    client_id: str
    client_secret: str
    introspection_api_key: str

    timeout: int = 30
    verify_ssl: bool = True
    max_retries: int = 3
