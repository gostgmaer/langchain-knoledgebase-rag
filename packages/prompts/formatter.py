from __future__ import annotations

def format_section(title: str, content: str) -> str:
    """
    Wraps a section of the prompt in a structured, consistent block format.
    
    Args:
        title: The section header.
        content: The text content of the section.
        
    Returns:
        A formatted string block.
    """
    return (
        f"--- {title} ---\n"
        f"{content.strip()}\n"
        f"-------------------"
    )
