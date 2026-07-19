class AIError(Exception):
    """Base AI exception."""


class ProviderNotSupportedError(AIError):
    """Raised when provider is unsupported."""


class ModelInitializationError(AIError):
    """Raised when model initialization fails."""

class InvalidProviderError(AIError):
    """Raised when an invalid provider is specified."""