"""Tests for the local .pptx reader.

``.pptx`` used to go through ``unstructured`` (libmagic + a first-use download), which
left the deck silently unindexed — the same failure as ``.docx`` (MODIFICATIONS §2.8)
and ``.xls`` (§2.9). The deck is generated here with python-pptx, so the test needs no
binary fixture and no fixture licence.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

from kotaemon.loaders import PptxReader


@pytest.fixture
def workdir():
    """Scratch directory (Path.mkdir, not mkdtemp: 0o700 dirs are not writable here)."""
    path = Path(tempfile.gettempdir()) / f"pptx-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def make_deck(path: Path) -> Path:
    """A three-shape deck: text slide, table + notes slide, and an empty slide."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()

    first = prs.slides.add_slide(prs.slide_layouts[1])  # title and content
    first.shapes.title.text = "学生综合素质积分管理办法"
    first.placeholders[1].text_frame.text = "满分 100 分，由五个部分组成。"

    second = prs.slides.add_slide(prs.slide_layouts[5])  # title only
    second.shapes.title.text = "加分标准"
    rows = [["项目", "分值"], ["国家级一等奖", "20"], ["省级一等奖", "10"]]
    table = second.shapes.add_table(
        len(rows), 2, Inches(1), Inches(2), Inches(6), Inches(2)
    ).table
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            table.cell(row_index, column_index).text = value
    second.notes_slide.notes_text_frame.text = "表格据 2025 版细则整理"

    prs.slides.add_slide(prs.slide_layouts[6])  # blank slide: no text at all

    prs.save(str(path))
    return path


def test_slides_become_documents_with_page_labels(workdir):
    deck = make_deck(workdir / "deck.pptx")

    documents = PptxReader().load_data(deck)

    # the blank slide is skipped: it contributes nothing to retrieval
    assert len(documents) == 2
    assert [doc.metadata["page_label"] for doc in documents] == [1, 2]
    assert "五个部分" in documents[0].text


def test_tables_are_rendered_as_csv(workdir):
    deck = make_deck(workdir / "deck.pptx")

    documents = PptxReader().load_data(deck)

    table_text = documents[1].text
    assert "项目,分值" in table_text.replace("\r", "")
    assert "国家级一等奖,20" in table_text.replace("\r", "")
    assert documents[1].metadata["slide_number"] == 2


def test_speaker_notes_are_kept(workdir):
    deck = make_deck(workdir / "deck.pptx")

    documents = PptxReader().load_data(deck)

    assert "[notes] 表格据 2025 版细则整理" in documents[1].text


def test_extra_info_is_merged_into_every_slide(workdir):
    deck = make_deck(workdir / "deck.pptx")

    documents = PptxReader().load_data(deck, extra_info={"file_name": "deck.pptx"})

    assert all(doc.metadata["file_name"] == "deck.pptx" for doc in documents)


def test_a_deck_without_text_still_yields_one_document(workdir):
    """An empty deck must not look like a failed parse to the file list / doctor."""
    from pptx import Presentation

    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])
    path = workdir / "blank.pptx"
    prs.save(str(path))

    documents = PptxReader().load_data(path)

    assert len(documents) == 1
    assert documents[0].text == ""
    assert documents[0].metadata["page_label"] == 1


def test_a_missing_file_raises_instead_of_returning_nothing(workdir):
    with pytest.raises(Exception):
        PptxReader().load_data(workdir / "nope.pptx")
