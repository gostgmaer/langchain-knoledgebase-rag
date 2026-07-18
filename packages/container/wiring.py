from __future__ import annotations

from .registry import container


def wire() -> None:
    """
    Wire dependencies.

    Routes and workers will be added here later.
    """
    container.wire(
        packages=[],
    )