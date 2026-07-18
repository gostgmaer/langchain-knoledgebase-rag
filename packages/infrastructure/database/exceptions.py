class DatabaseError(Exception):
    """Base database exception."""


class EntityNotFoundError(DatabaseError):
    """Raised when an entity is not found."""


class DuplicateEntityError(DatabaseError):
    """Raised when a unique constraint is violated."""


class TransactionError(DatabaseError):
    """Raised when a transaction fails."""