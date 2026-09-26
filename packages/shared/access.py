"""
Per-request access clearance, readable anywhere below the request without threading arguments.

`can_read_restricted()` defaults to False: any code path that runs outside an authenticated request
(a worker job, a script, a test) sees only unrestricted documents. The authentication middleware
raises it to True for administrators (and for anonymous development mode when AUTH_REQUIRED is off).
"""

from __future__ import annotations

from contextvars import ContextVar, Token

_can_read_restricted: ContextVar[bool] = ContextVar("can_read_restricted", default=False)


def can_read_restricted() -> bool:
    return _can_read_restricted.get()


def set_can_read_restricted(value: bool) -> Token:
    return _can_read_restricted.set(value)
