# Tool decorators
_TOOL_REGISTRY = {}


def register_tool(name: str):

    def wrapper(cls):

        _TOOL_REGISTRY[name] = cls

        return cls

    return wrapper