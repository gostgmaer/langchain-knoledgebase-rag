class GraphException(Exception):
    """Base graph exception."""


class GraphCompilationException(
    GraphException,
):
    """Raised when graph compilation fails."""


class GraphExecutionException(
    GraphException,
):
    """Raised when graph execution fails."""


class RouterException(
    GraphException,
):
    """Raised when routing fails."""