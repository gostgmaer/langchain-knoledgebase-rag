# Logging context
from contextvars import ContextVar

request_id = ContextVar("request_id", default=None)
tenant_id = ContextVar("tenant_id", default=None)
user_id = ContextVar("user_id", default=None)
conversation_id = ContextVar("conversation_id", default=None)
trace_id = ContextVar("trace_id", default=None)