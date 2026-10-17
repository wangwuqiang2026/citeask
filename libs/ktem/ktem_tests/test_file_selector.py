"""Tests for the Chat page file-selector helpers."""

from __future__ import annotations

from typing import Any, Optional

import pytest
from ktem.utils.selector import (
    DEFAULT_SELECTOR_MODE,
    SELECTOR_CHOICES,
    SELECTOR_MODE_ALL,
    SELECTOR_MODE_DISABLED,
    SELECTOR_MODE_SELECT,
    SELECTOR_STATE_SENTINEL,
    resolve_selector_user_id,
)


def test_default_mode_is_offered_to_the_user() -> None:
    """The selector must start in a mode the radio actually offers.

    A default outside ``SELECTOR_CHOICES`` renders the radio as "nothing
    selected". The mode is then never resolved, the retriever receives an empty
    file list and skips retrieval entirely, so answers silently come from the
    LLM's own memory instead of the indexed documents.
    """
    assert DEFAULT_SELECTOR_MODE in SELECTOR_CHOICES
    assert SELECTOR_MODE_DISABLED not in SELECTOR_CHOICES


def test_choices_cover_exactly_the_usable_modes() -> None:
    """Both usable modes are offered; the "no retrieval" mode is not."""
    assert set(SELECTOR_CHOICES) == {SELECTOR_MODE_ALL, SELECTOR_MODE_SELECT}


@pytest.mark.parametrize(
    ("session_user_id", "selector_user_id", "expected"),
    (
        # the session's id wins over the stale widget state ...
        ("user-1", SELECTOR_STATE_SENTINEL, "user-1"),
        ("user-1", None, "user-1"),
        ("user-1", "user-stale", "user-1"),
        # ... and the widget state is only a fallback
        (None, "user-1", "user-1"),
        (None, SELECTOR_STATE_SENTINEL, SELECTOR_STATE_SENTINEL),
        (None, None, None),
    ),
)
def test_resolve_selector_user_id(
    session_user_id: Optional[Any],
    selector_user_id: Optional[Any],
    expected: Optional[Any],
) -> None:
    """The authoritative user id takes precedence over the selector's own state.

    The selector's ``gr.State`` is seeded with a sentinel and is only refreshed
    when the mode radio fires its change event, so a fresh session used to scope
    "Search All" to an id that matches no file, returning no documents.
    """
    assert resolve_selector_user_id(session_user_id, selector_user_id) == expected


@pytest.mark.parametrize(
    ("session_user_id", "selector_user_id"),
    (
        ("10c2b1f0", SELECTOR_STATE_SENTINEL),
        ("10c2b1f0", None),
    ),
)
def test_stale_selector_state_does_not_leak_into_the_query(
    session_user_id: str, selector_user_id: Any
) -> None:
    """A real session never queries with the sentinel value."""
    assert (
        resolve_selector_user_id(session_user_id, selector_user_id)
        != SELECTOR_STATE_SENTINEL
    )
