# Empty file
class ApplicationError(Exception):
    """Base application exception."""


class ValidationError(ApplicationError):
    """Business validation failed."""


class ResourceNotFoundError(ApplicationError):
    """Requested resource not found."""


class ConflictError(ApplicationError):
    """Resource conflict."""