from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class DailyUsageSchema(BaseModel):
    date: str
    total_tokens: int
    cost: Decimal


class UsageResponseSchema(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: Decimal
    daily: list[DailyUsageSchema] = []
