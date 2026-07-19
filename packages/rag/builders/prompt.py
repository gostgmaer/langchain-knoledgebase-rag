# prompt.py
"""
RAG prompt builder.
"""

from __future__ import annotations

from packages.rag.exceptions import PromptBuildError
from packages.rag.schemas import Context
from packages.rag.schemas import RAGRequest


class PromptBuilder:
    """
    Builds the final prompt for the language model.
    """

    DEFAULT_SYSTEM_PROMPT = (
        "You are a helpful AI assistant.\n"
        "Answer the user's question using only the provided context.\n"
        "If the answer cannot be found in the context, clearly say you don't know.\n"
        "Do not make up information."
    )

    def build(
        self,
        request: RAGRequest,
        context: Context,
    ) -> str:
        """
        Build the final prompt.
        """

        if not request.query.strip():
            raise PromptBuildError(
                "Query cannot be empty."
            )

        system_prompt = (
            request.system_prompt
            or self.DEFAULT_SYSTEM_PROMPT
        )

        return f"""{system_prompt}

==============================
CONTEXT
==============================

{context.text}

==============================
QUESTION
==============================

{request.query}

==============================
ANSWER
==============================
"""