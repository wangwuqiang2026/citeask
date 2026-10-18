"""Tests for mapping a clicked file-list row to its file id.

The file list no longer shows an ``id`` column (it means nothing to the user), so the
row handler reads the id from the *state* records the table was built from. That
indirection is what keeps row selection working after the column was removed
(MODIFICATIONS §5.18).
"""

from __future__ import annotations

from types import SimpleNamespace

from ktem.index.file.ui import FileIndexPage


def page():
    return SimpleNamespace(
        selected_panel_false="Selected file: (please select above)",
        selected_panel_true="Selected file: {name}",
    )


def records():
    return [
        {"id": "id-a", "name": "a.pdf"},
        {"id": "id-b", "name": "b.xlsx"},
    ]


def event(index=(0, 0), selected=True, value="a.pdf"):
    return SimpleNamespace(index=index, selected=selected, value=value)


def test_clicking_a_row_returns_the_id_from_the_state_records():
    file_id, panel = FileIndexPage.interact_file_list(page(), records(), event((1, 1)))

    assert file_id == "id-b"
    assert panel == "Selected file: b.xlsx"


def test_the_panel_keeps_the_placeholder_until_a_row_is_selected():
    file_id, panel = FileIndexPage.interact_file_list(
        page(), records(), event((0, 0), selected=False)
    )

    assert file_id is None
    assert panel == "Selected file: (please select above)"


def test_an_empty_list_is_handled_without_indexing():
    """Before anything is uploaded the state is empty; clicking it must not crash."""
    file_id, panel = FileIndexPage.interact_file_list(page(), [], event((0, 0)))

    assert file_id is None
    assert panel == "Selected file: (please select above)"


def test_an_out_of_range_row_is_ignored():
    """A stale click can arrive after a filter shrank the list."""
    file_id, panel = FileIndexPage.interact_file_list(page(), records(), event((7, 0)))

    assert file_id is None
    assert panel == "Selected file: (please select above)"
