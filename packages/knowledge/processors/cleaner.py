# cleaner.py
from __future__ import annotations

import re


from langchain_core.documents import Document
from .base import DocumentProcessor


class DocumentCleaner(DocumentProcessor):

    async def process(
        self,
        documents: list[Document],
    ) -> list[Document]:

        cleaned = []

        for document in documents:

            text = document.page_content

            text = text.replace("\r\n", "\n")
            text = text.replace("\r", "\n")

            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"[ ]{2,}", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = "\n".join(line.rstrip() for line in text.split("\n"))

            document.page_content = text.strip()

            cleaned.append(document)

        return cleaned