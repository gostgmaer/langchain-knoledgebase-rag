from enum import StrEnum


class ConversationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"
    # Set for the duration of one graph invoke()/resume() call (Durable
    # Execution, docs/mvpRAG.md v2.0) — see Conversation.processing_
    # started_at's own docstring for why this, paired with that
    # timestamp, is what lets recover_stuck_conversations_job tell a
    # genuinely crashed turn apart from a conversation nobody has
    # replied to in a while.
    PROCESSING = "PROCESSING"