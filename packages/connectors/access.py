"""
External permissions -> the platform's document access.

The external system says who may read an item (users, groups). Those ids are the EXTERNAL system's; they are
never assumed to equal internal user ids. An administrator maps them (IdentityMapping) to internal users or
roles, and the result is written to the document's `visibility` / `allowed_roles` / `allowed_users`, which the
retrieval query already enforces. Rules are kept (DocumentAccessRule) so access can be re-derived when a mapping
changes, without contacting the source again.

Fail closed: an item with explicit permissions is restricted; a principal with no mapping grants nothing, so an
item whose principals are all unmapped is readable by administrators only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.connectors.models import ExternalPermission
from packages.domain.models.document import Document
from packages.domain.models.knowledge_source import DocumentAccessRule, IdentityMapping, KnowledgeSource


@dataclass
class DerivedAccess:
    visibility: str
    allowed_roles: list[str] = field(default_factory=list)
    allowed_users: list[str] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)


def permissions_hash(permissions: list[ExternalPermission] | None) -> str:
    """Stable fingerprint; None (unknown) and [] (no restriction) are different states."""
    if permissions is None:
        return "unknown"
    rows = sorted((p.principal_type, p.principal_id, p.permission) for p in permissions)
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def default_access(configuration: dict[str, Any]) -> DerivedAccess:
    visibility = configuration.get("default_visibility") or "tenant"
    roles = list(configuration.get("default_allowed_roles") or []) if visibility == "restricted" else []
    return DerivedAccess(visibility=visibility, allowed_roles=roles)


async def derive_access(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    provider: str,
    rules: list[tuple[str, str, str]] | None,
    configuration: dict[str, Any],
) -> DerivedAccess:
    """`rules` = [(principal_type, external principal id, permission)], or None when the source cannot tell."""
    if not rules:
        return default_access(configuration)  # unknown, or "no page-level restriction": the source default applies

    readers = [(t, p) for t, p, perm in rules if perm in ("read", "write", "admin")]
    ids = sorted({p for _, p in readers})
    mappings: dict[tuple[str, str], IdentityMapping] = {}
    if ids:
        found = (
            await session.execute(
                select(IdentityMapping).where(
                    IdentityMapping.tenant_id == tenant_id,
                    IdentityMapping.provider == provider,
                    IdentityMapping.external_id.in_(ids),
                )
            )
        ).scalars().all()
        mappings = {("group" if m.principal_type != "user" else "user", m.external_id): m for m in found}

    access = DerivedAccess(visibility="restricted")
    for principal_type, principal_id in readers:
        kind = "user" if principal_type == "user" else "group"
        mapping = mappings.get((kind, principal_id))
        if mapping is None:
            access.unmapped.append(principal_id)
        elif mapping.internal_type == "user":
            access.allowed_users.append(mapping.internal_id)
        else:
            access.allowed_roles.append(mapping.internal_id)
    access.allowed_roles = sorted(set(access.allowed_roles))
    access.allowed_users = sorted(set(access.allowed_users))
    access.unmapped = sorted(set(access.unmapped))
    return access


def apply_access(document: Document, access: DerivedAccess) -> None:
    document.visibility = access.visibility
    document.allowed_roles = access.allowed_roles or None
    document.allowed_users = access.allowed_users or None


async def replace_rules(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    source_id: UUID,
    document_id: UUID,
    permissions: list[ExternalPermission],
) -> None:
    await session.execute(delete(DocumentAccessRule).where(DocumentAccessRule.document_id == document_id, DocumentAccessRule.tenant_id == tenant_id))
    for p in permissions:
        session.add(
            DocumentAccessRule(
                tenant_id=tenant_id,
                source_id=source_id,
                document_id=document_id,
                principal_type=p.principal_type,
                principal_id=p.principal_id[:512],
                permission=p.permission,
            )
        )


async def remap_access(session: AsyncSession, *, tenant_id: UUID, provider: str) -> int:
    """Re-derives access for every current document of this provider after identity mappings changed. Returns documents updated."""
    sources = {
        s.id: s
        for s in (
            await session.execute(select(KnowledgeSource).where(KnowledgeSource.tenant_id == tenant_id, KnowledgeSource.type == provider))
        ).scalars()
    }
    if not sources:
        return 0
    rows = (
        await session.execute(
            select(DocumentAccessRule, Document)
            .join(Document, Document.id == DocumentAccessRule.document_id)
            .where(DocumentAccessRule.tenant_id == tenant_id, DocumentAccessRule.source_id.in_(list(sources)), Document.is_current.is_(True))
        )
    ).all()
    grouped: dict[UUID, tuple[Document, list[tuple[str, str, str]]]] = {}
    for rule, document in rows:
        grouped.setdefault(document.id, (document, []))[1].append((rule.principal_type, rule.principal_id, rule.permission))

    changed = 0
    for document, rules in grouped.values():
        access = await derive_access(session, tenant_id=tenant_id, provider=provider, rules=rules, configuration=sources[document.source_id].configuration or {})
        before = (document.visibility, document.allowed_roles, document.allowed_users)
        apply_access(document, access)
        if before != (document.visibility, document.allowed_roles, document.allowed_users):
            changed += 1
    return changed
