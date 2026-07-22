from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class FeatureSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    enable_rag: bool = True

    enable_tools: bool = True

    enable_memory: bool = True

    enable_streaming: bool = True

    enable_reranking: bool = True

    enable_query_rewrite: bool = True

    enable_web_search: bool = True

    enable_weather: bool = True

    enable_news: bool = True

    enable_calculator: bool = True

    # Master kill-switch for real RBAC enforcement (packages/api/dependencies.py's
    # require_permission()/require_role()). Off by default — those dependencies
    # exist and are correct, but nothing currently attaches them to a route, and
    # flipping this on doesn't change that by itself. When True, a route that
    # actually uses one of them enforces for real (401 with no verified user,
    # 403 without the required role/permission) instead of no-op'ing. Doesn't
    # touch AuthenticationMiddleware's own fail-open identity resolution either
    # way — anonymous default-tenant access to routes that don't require a
    # permission keeps working regardless of this flag.
    enable_rbac: bool = False