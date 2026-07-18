# Log processors
import structlog

from .context import (
    conversation_id,
    request_id,
    tenant_id,
    trace_id,
    user_id,
)


def add_context(
    logger,
    method_name,
    event_dict,
):
    event_dict["request_id"] = request_id.get()
    event_dict["tenant_id"] = tenant_id.get()
    event_dict["user_id"] = user_id.get()
    event_dict["conversation_id"] = conversation_id.get()
    event_dict["trace_id"] = trace_id.get()

    return event_dict