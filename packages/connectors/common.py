"""Settings every source has, whatever its connector: where documents land, how they are chunked, who may read them."""

from __future__ import annotations

from typing import Any

from packages.connectors.base import ConfigField

COMMON_FIELDS: tuple[ConfigField, ...] = (
    ConfigField("default_visibility", "Who can retrieve these documents", "select", default="tenant", options=("tenant", "restricted"), group="permissions",
                help="'tenant' = every member. 'restricted' = administrators plus the roles below. Applies when the source gives no page-level permissions."),
    ConfigField("default_allowed_roles", "Roles allowed when restricted", "string_list", group="permissions", help="IAM role names, e.g. finance."),
    ConfigField("permission_mode", "Permission behaviour", "select", default="sync_external", options=("sync_external", "source_default"), group="permissions",
                help="sync_external: follow the source's own permissions (needs identity mappings). source_default: ignore them and use the setting above."),
    ConfigField("chunking_strategy", "Chunking", "select", default="recursive", options=("recursive", "markdown", "semantic", "auto"), group="advanced"),
    ConfigField("allow_bulk_delete", "Allow removing most documents in one sync", "boolean", default=False, group="advanced",
                help="Off = a sync that would remove more than half of a large source is held back as a safety net."),
)
COMMON_KEYS = {f.key for f in COMMON_FIELDS}


def split_config(configuration: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """(common settings, connector-specific settings)."""
    common = {k: v for k, v in configuration.items() if k in COMMON_KEYS}
    specific = {k: v for k, v in configuration.items() if k not in COMMON_KEYS}
    return common, specific
