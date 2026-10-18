"""Rendering of the per-file profile ("what is this file about").

Indexing stores a short profile in ``Source.note["summary"]`` (see
:mod:`ktem.index.file.routing`), which file routing compares against a question. It is
also the only human-readable answer to "what did the app understand this file to be",
so the file list shows it — one collapsed line, because the stored profile contains the
file name and three excerpts.
"""

from __future__ import annotations

from typing import Any, Optional

#: Longest single-line excerpt shown in the file list.
DEFAULT_PROFILE_LIMIT = 90


def profile_text(summary: Optional[str]) -> str:
    """The profile body, without the redundant ``文件：<name>`` prefix."""
    if not summary:
        return ""
    text = " ".join(str(summary).split())
    marker = "内容摘录："
    if marker in text:
        text = text.split(marker, 1)[1]
    return text.strip()


def describe_profile(
    note: Any, limit: int = DEFAULT_PROFILE_LIMIT, suffix: str = "..."
) -> str:
    """One-line description of a file for the list, or ``-`` when it has none.

    Files indexed before profiles existed have none until the first retrieval fills
    one in, which is why this is ``-`` rather than an error.

    ``suffix`` is what marks a shortened excerpt; the file list passes ``""`` so the
    table shows the text itself instead of an ellipsis (the full profile is in the
    detail panel below the table).
    """
    summary = note.get("summary") if isinstance(note, dict) else None
    text = profile_text(summary)
    if not text:
        return "-"
    if limit > 0 and len(text) > limit:
        return text[:limit].rstrip() + suffix
    return text
