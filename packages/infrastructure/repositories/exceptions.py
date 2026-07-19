# Exceptions
class RepositoryError(Exception):
    """Base repository exception."""


class EntityNotFoundError(RepositoryError):
    """Entity was not found."""


class DuplicateEntityError(RepositoryError):
    """Duplicate entity."""


class InvalidFilterError(RepositoryError):
    """Invalid filter."""


class InvalidOrderingError(RepositoryError):
    """Invalid ordering."""