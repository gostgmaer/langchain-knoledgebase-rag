"""
Stores and reads connector credentials. The only code that ever handles a plaintext secret besides the connector
that uses it. Nothing here returns or logs one: `status` describes a credential without revealing it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.config.loader import settings
from packages.connectors.credentials import CredentialCipher
from packages.domain.models.knowledge_source import KnowledgeSource, SourceCredential


class CredentialScopeError(PermissionError):
    """A credential was requested for a source it does not belong to (or another tenant)."""


class SourceCredentialService:
    def __init__(self, cipher: CredentialCipher | None = None) -> None:
        self._cipher = cipher

    @property
    def cipher(self) -> CredentialCipher:
        # Built lazily so the API starts without a key; only credential operations need one.
        if self._cipher is None:
            self._cipher = CredentialCipher(settings.rag.connector_credential_keys)
        return self._cipher

    async def _row(self, session: AsyncSession, source: KnowledgeSource) -> SourceCredential | None:
        row = (
            await session.execute(select(SourceCredential).where(SourceCredential.source_id == source.id))
        ).scalar_one_or_none()
        if row is not None and (row.tenant_id != source.tenant_id or row.source_id != source.id):
            raise CredentialScopeError("Credential does not belong to this source.")
        return row

    async def store(self, session: AsyncSession, source: KnowledgeSource, *, kind: str, secret: dict[str, Any], actor_id: UUID | None) -> None:
        """Creates or replaces (rotates) the source's credential."""
        ciphertext = self.cipher.encrypt(secret)
        row = await self._row(session, source)
        now = datetime.now(UTC)
        if row is None:
            session.add(SourceCredential(tenant_id=source.tenant_id, source_id=source.id, kind=kind, ciphertext=ciphertext, created_by=actor_id))
        else:
            row.kind, row.ciphertext, row.revoked_at = kind, ciphertext, None
            row.rotated_at = now
            row.key_version = (row.key_version or 1) + 1
        await session.flush()

    async def load(self, session: AsyncSession, source: KnowledgeSource) -> dict[str, Any] | None:
        row = await self._row(session, source)
        if row is None or row.revoked_at is not None or not row.ciphertext:
            return None
        return self.cipher.decrypt(row.ciphertext)

    async def revoke(self, session: AsyncSession, source: KnowledgeSource) -> bool:
        row = await self._row(session, source)
        if row is None:
            return False
        row.ciphertext = None  # the secret is destroyed, not merely flagged
        row.revoked_at = datetime.now(UTC)
        await session.flush()
        return True

    async def reencrypt(self, session: AsyncSession, source: KnowledgeSource) -> bool:
        """Re-encrypts under the primary key (after adding a new key to CONNECTOR_CREDENTIAL_KEYS)."""
        row = await self._row(session, source)
        if row is None or not row.ciphertext:
            return False
        row.ciphertext = self.cipher.rotate(row.ciphertext)
        row.rotated_at = datetime.now(UTC)
        await session.flush()
        return True

    async def status(self, session: AsyncSession, source: KnowledgeSource) -> dict[str, Any]:
        row = await self._row(session, source)
        return {
            "configured": bool(row and row.ciphertext and not row.revoked_at),
            "kind": row.kind if row else None,
            "revoked": bool(row and row.revoked_at),
            "updated_at": (row.rotated_at or row.created_at) if row else None,
        }
