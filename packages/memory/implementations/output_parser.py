"""
packages/memory/implementations/output_parser.py

A real LangChain output parser for memory extraction — turns the LLM's
free-text JSON response into a list of plain dicts, ready to become
MemoryFact objects. Used as the last stage of an LCEL chain
(prompt | llm | parser), not called directly.
"""

from __future__ import annotations

import json

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import BaseOutputParser

from packages.shared.messages import strip_code_fence


class MemoryFactListParser(BaseOutputParser[list[dict]]):
    """
    Parses an LLM's memory-extraction output into a list of raw dicts.

    Relies on BaseOutputParser's default parse_result(), which reads
    `Generation.text` — LangChain's own content accessor already
    normalizes provider-specific shapes (e.g. Gemini's list-of-blocks
    content) into a plain string before parse() ever sees it.
    """

    def parse(self, text: str) -> list[dict]:
        cleaned = strip_code_fence(text.strip())

        if not cleaned:
            return []

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise OutputParserException(
                f"Could not parse memory extraction output as JSON: {text[:200]!r}"
            ) from exc

        if not isinstance(data, list):
            raise OutputParserException(
                f"Expected a JSON list of memory items, got {type(data).__name__}"
            )

        return data

    @property
    def _type(self) -> str:
        return "memory_fact_list"
