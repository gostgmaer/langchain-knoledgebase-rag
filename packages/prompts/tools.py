from __future__ import annotations

def build_tools_section(tools: list[str]) -> str:
    """
    Formats the available tools and their usage instructions for the prompt.
    """
    if not tools:
        return ""
        
    lines = ["You have access to the following tools. Use them to help fulfill the user's request if needed:\n"]
    for tool in tools:
        lines.append(f"- {tool}")
        
    return "\n".join(lines)
