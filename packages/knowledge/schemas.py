from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


@dataclass(slots=True)
class IngestionRequest:

    tenant_id: UUID

    model_profile_id: UUID

    file: Path

    document_name: str

    metadata: dict[str, object] | None = None