# Tools exceptions
class ToolException(Exception):
    """Base tool exception."""


class ToolNotFoundException(
    ToolException,
):
    """Tool not found."""


class ToolExecutionException(
    ToolException,
):
    """Execution failed."""


class ToolValidationException(
    ToolException,
):
    """Validation failed."""