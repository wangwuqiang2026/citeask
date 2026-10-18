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


def resolve_selection(
    mode: Any, selected: Any, all_file_ids: list[Any]
) -> list[Any]:
    """The file ids a retrieval should be scoped to.

    "Search in File(s)" with an **empty** dropdown is not a request to search
    nothing: it happens after the file list is refreshed (an upload rewrites the
    dropdown's choices and clears its value), and returning ``[]`` here made the
    retriever skip retrieval entirely — the chat then said "the knowledge base has no
    evidence (best match 0.00)" about a corpus that answers fine (MODIFICATIONS §5.16).
    An empty selection therefore falls back to every file, which is also what the user
    expected before the refresh.

    Args:
        mode: the selector's mode (``all`` / ``select`` / ``disabled``).
        selected: the dropdown value; may be ``None``, a string or a list.
        all_file_ids: every file id the current user owns.

    Returns:
        The file ids to scope the retrieval to (empty only for ``disabled``).
    """
    if mode == SELECTOR_MODE_DISABLED:
        return []
    if mode != SELECTOR_MODE_SELECT:
        return list(all_file_ids)

    if selected is None:
        chosen: list[Any] = []
    elif isinstance(selected, (list, tuple, set)):
        chosen = [item for item in selected if item not in (None, "")]
    elif isinstance(selected, str):
        chosen = [selected] if selected else []
    else:
        chosen = [selected]

    return chosen if chosen else list(all_file_ids)
