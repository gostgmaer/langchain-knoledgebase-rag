# Conversation exceptions
class ConversationException(Exception):
    """Base conversation exception."""


class ConversationNotFoundException(
    ConversationException,
):
    """Conversation not found."""


class MessageNotFoundException(
    ConversationException,
):
    """Message not found."""


class ConversationClosedException(
    ConversationException,
):
    """Conversation is closed."""


class InvalidConversationException(
    ConversationException,
):
    """Conversation is invalid."""