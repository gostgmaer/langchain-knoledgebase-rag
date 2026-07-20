from __future__ import annotations

def build_rag_section(documents: list[str]) -> str:
    """
    Formats retrieved semantic documents for inclusion in the prompt.
    """
    if not documents:
        return ""
        
    lines = ["The following context was retrieved from the knowledge base to help you answer the user's query:\n"]
    for i, doc in enumerate(documents, 1):
        lines.append(f"[Document {i}]")
        lines.append(f"{doc}\n")
        
    return "\n".join(lines)
