# Memory session
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Session:
    session_id: str
    created_at: datetime
    updated_at: datetime