"""
packages/shared/messages.py

Some providers (notably Gemini via langchain-google-genai) return
AIMessage.content as a list of content blocks instead of a plain string.
Anything that treats .content as text (DB persistence, JSON parsing,
prompt building) needs it flattened first.
"""

from __future__ import annotations

import re

_CODE_FENCE = re.compile(r"^```[a-zA-Z]*\n|\n```$")


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
