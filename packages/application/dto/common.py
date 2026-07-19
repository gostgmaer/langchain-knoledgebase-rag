# Empty file
from __future__ import annotations

from pydantic import BaseModel


class PaginationRequest(BaseModel):
    page: int = 1
    size: int = 20


class PaginationResponse(BaseModel):
    page: int
    size: int
    total: int
    pages: int