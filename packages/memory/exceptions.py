class MemoryException(Exception):
    """Base memory exception."""


class CheckpointException(
    MemoryException,
):
    """Checkpoint error."""


class SessionNotFoundException(
    MemoryException,
):
    """Session not found."""