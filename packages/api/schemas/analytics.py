from __future__ import annotations

from pydantic import BaseModel


class QueriesPerDaySchema(BaseModel):
    date: str
    count: int


class FeedbackTrendSchema(BaseModel):
    date: str
    rating: str
    count: int


class TopFailingQuerySchema(BaseModel):
    message_id: str
    content: str
    negative_count: int


class AnalyticsSummarySchema(BaseModel):
    queries_per_day: list[QueriesPerDaySchema]
    feedback_trends: list[FeedbackTrendSchema]
    top_failing_queries: list[TopFailingQuerySchema]
