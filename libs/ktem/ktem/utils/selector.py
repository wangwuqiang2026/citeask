"""Helpers for the file-selector widget of the Chat page.

The selector is a radio (retrieval scope) plus a dropdown (chosen files) and a
``gr.State`` carrying the user id. Keeping its decisions here as plain functions
makes them unit-testable without pulling Gradio and the application database in.
"""

from __future__ import annotations

from typing import Any, Optional

#: Search across every file the current user owns.
SELECTOR_MODE_ALL = "all"
#: Search only within the files picked in the dropdown.
SELECTOR_MODE_SELECT = "select"
#: Do not scope retrieval to files at all.
SELECTOR_MODE_DISABLED = "disabled"

#: The modes offered to the user, i.e. the radio choices.
SELECTOR_CHOICES = (SELECTOR_MODE_ALL, SELECTOR_MODE_SELECT)

#: Mode the selector starts in.
#:
#: Must be one of :data:`SELECTOR_CHOICES`: a radio whose value is not among its
#: choices renders as *nothing selected*, and an unresolved mode leaves the
#: retriever with an empty file list and skips retrieval altogether, so the
#: answer silently comes from the LLM's own memory instead of the documents.
DEFAULT_SELECTOR_MODE = SELECTOR_MODE_ALL

#: Sentinel seeded into the selector's ``gr.State`` before the user interacts.
SELECTOR_STATE_SENTINEL = -1


def resolve_selector_user_id(
    session_user_id: Any, selector_user_id: Any
) -> Optional[Any]:
    """Return the user id a file-selector query should be scoped to.

    The selector keeps its own ``gr.State`` copy of the user id, but that state
    is seeded with :data:`SELECTOR_STATE_SENTINEL` and is only refreshed when the
    mode radio fires its change event. In a fresh session it is therefore stale,
    while the session already carries the authoritative id (the chat pipeline
    passes it down). Prefer the session id and fall back to the widget state only
    when the session has none.

    Args:
        session_user_id: user id carried by the current session/request.
        selector_user_id: value currently held by the selector's ``gr.State``.

    Returns:
        The user id to query with, or ``None`` when neither is available.
    """
    if session_user_id is not None:
        return session_user_id
    return selector_user_id
