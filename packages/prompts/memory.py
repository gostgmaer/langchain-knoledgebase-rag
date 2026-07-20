from __future__ import annotations

from typing import Any

def build_memory_section(memory_data: dict[str, Any]) -> str:
    """
    Formats the memory data into a structured string for the prompt.
    """
    if not memory_data:
        return ""

    lines = []
    if "profile" in memory_data and memory_data["profile"]:
        lines.append(f"- User Profile: {memory_data['profile']}")
        
    if "preferences" in memory_data and memory_data["preferences"]:
        lines.append(f"- Preferences: {memory_data['preferences']}")
        
    if "facts" in memory_data and memory_data["facts"]:
        lines.append("- Remembered Facts:")
        for fact in memory_data["facts"]:
            lines.append(f"  * {fact}")
            
    if "summary" in memory_data and memory_data["summary"]:
        lines.append(f"- Previous Conversation Summary: {memory_data['summary']}")

    return "\n".join(lines)
