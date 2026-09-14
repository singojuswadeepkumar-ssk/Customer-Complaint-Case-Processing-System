"""Shared helpers for working with LangChain LLM responses."""

from typing import Any


def extract_text_content(content: Any) -> str:
    """
    Normalize a LangChain message ``content`` payload into a plain string.

    Newer versions of ``langchain-google-genai`` may return content as a
    list of content blocks (e.g. ``[{"type": "text", "text": "..."}]``)
    instead of a plain string. This helper handles both formats safely.

    Args:
        content: The raw ``.content`` attribute from an LLM response message.

    Returns:
        Plain text string extracted from the content payload.
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
        return "".join(parts)

    return str(content)
