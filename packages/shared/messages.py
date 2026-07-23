"""
packages/shared/messages.py

Some providers (notably Gemini via langchain-google-genai) return
AIMessage.content as a list of content blocks instead of a plain string.
Anything that treats .content as text (DB persistence, JSON parsing,
prompt building) needs it flattened first.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import BaseMessage

_CODE_FENCE = re.compile(r"^```[a-zA-Z]*\n|\n```$")

# ormsgpack (LangGraph's checkpoint serializer) rejects any Python int
# outside signed 64-bit range with a hard TypeError, not a warning —
# it crashes the whole turn mid-checkpoint. A tool-declared `str`
# parameter (e.g. calculator's `expression`) doesn't stop a provider
# from occasionally emitting a bare numeric literal instead of a
# quoted string for a large number; that literal survives untouched
# into AIMessage.tool_calls[i]["args"] and blows up at checkpoint time,
# not at tool-call time, which is what made this hard to trace back.
_INT64_MAX = 2**63 - 1
_INT64_MIN = -(2**63)


def normalize_message_content(content: str | list) -> str:
    if isinstance(content, str):
        return content

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            parts.append(str(block.get("text", "")))

    return "".join(parts)


def strip_code_fence(text: str) -> str:
    return _CODE_FENCE.sub("", text.strip()).strip()


def _sanitize_arg_value(value: Any) -> Any:
    if isinstance(value, int) and not isinstance(value, bool) and not (_INT64_MIN <= value <= _INT64_MAX):
        return str(value)
    if isinstance(value, dict):
        return {k: _sanitize_arg_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_arg_value(v) for v in value]
    return value


def sanitize_tool_call_args(message: BaseMessage) -> BaseMessage:
    """
    Stringifies any out-of-64-bit-range integer in `message.tool_calls`
    args in place, so a provider-emitted numeric literal can never
    reach the checkpointer as a raw Python int. Every other value is
    left untouched — this only fires for the specific shape that
    actually crashes `ormsgpack`.
    """

    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        return message

    for call in tool_calls:
        args = call.get("args")
        if isinstance(args, dict):
            call["args"] = _sanitize_arg_value(args)

    return message
