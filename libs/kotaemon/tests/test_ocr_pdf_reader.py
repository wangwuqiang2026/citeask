"""Tests for the OCR-aware PDF reader.

The OCR engine is replaced by a stub, so the suite stays offline and fast: what
is being tested is the per-page decision (text layer vs OCR) and the metadata
that the citation panel depends on.
"""

from __future__ import annotations

import fitz
import pytest
from kotaemon.loaders import ocr_pdf_loader
from kotaemon.loaders.ocr_pdf_loader import OCRPDFReader

LONG_TEXT = "This page already carries a real text layer. " * 10  # ~460 chars
SHORT_TEXT = "Chapter title"


def make_pdf(path, pages):
    """Write a small PDF whose pages contain the given text (ASCII only)."""
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        if text:
            # insert_textbox wraps; insert_text would draw one line off the page
            page.insert_textbox(fitz.Rect(72, 72, 520, 760), text, fontsize=8)
    doc.save(str(path))
    doc.close()
    return path


class FakeEngine:
    """Stand-in for RapidOCR: returns one line of text and counts the calls."""

    def __init__(self, text="recognized page text"):
        self.text = text
        self.calls = 0

    def __call__(self, image):
        self.calls += 1
        return ([[[0, 0, 1, 1], self.text, 0.99]], None)


@pytest.fixture
def engine(monkeypatch):
    fake = FakeEngine()
    monkeypatch.setattr(ocr_pdf_loader, "get_ocr_engine", lambda: fake)
    return fake


def test_a_real_text_layer_is_kept_and_not_ocrd(tmp_path, engine) -> None:
    pdf = make_pdf(tmp_path / "digital.pdf", [LONG_TEXT, LONG_TEXT])

    documents = OCRPDFReader(min_text_chars=200).load_data(pdf)

    assert len(documents) == 2
    assert engine.calls == 0
    # the text layer may be re-wrapped by the PDF reader, so compare words
    assert documents[0].text.split() == LONG_TEXT.split()
    assert documents[0].metadata["ocr"] is False


def test_a_page_without_a_text_layer_is_ocrd(tmp_path, engine) -> None:
    pdf = make_pdf(tmp_path / "scanned.pdf", [SHORT_TEXT, SHORT_TEXT])

    documents = OCRPDFReader(min_text_chars=200).load_data(pdf)

    assert len(documents) == 2
    assert engine.calls == 2
    assert documents[0].text == "recognized page text"
    assert documents[0].metadata["ocr"] is True


def test_metadata_supports_the_citation_panel(tmp_path, engine) -> None:
    pdf = make_pdf(tmp_path / "meta.pdf", [SHORT_TEXT])

    document = OCRPDFReader(min_text_chars=200).load_data(
        pdf, extra_info={"file_id": "abc", "collection_name": "index_1"}
    )[0]

    metadata = document.metadata
    # Render.preview() needs a real path and the PDF mime type for the [Preview] link
    assert metadata["file_path"] == str(pdf)
    assert metadata["file_type"] == "application/pdf"
    assert metadata["file_name"] == "meta.pdf"
    # sorting and int() in the UI expect a numeric page label
    assert metadata["page_label"] == "1"
    assert metadata["file_id"] == "abc"
    assert metadata["collection_name"] == "index_1"


def test_the_text_layer_wins_when_ocr_returns_nothing(tmp_path, monkeypatch) -> None:
    """A failing OCR must not delete the little text the page does have."""
    empty = FakeEngine(text="")
    monkeypatch.setattr(ocr_pdf_loader, "get_ocr_engine", lambda: empty)
    pdf = make_pdf(tmp_path / "empty.pdf", [SHORT_TEXT])

    document = OCRPDFReader(min_text_chars=200).load_data(pdf)[0]

    assert document.text == SHORT_TEXT
    assert document.metadata["ocr"] is False


def test_reader_still_works_without_the_engine(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ocr_pdf_loader, "get_ocr_engine", lambda: None)
    pdf = make_pdf(tmp_path / "noengine.pdf", [LONG_TEXT, SHORT_TEXT])

    documents = OCRPDFReader(min_text_chars=200).load_data(pdf)

    assert [len(d.text) > 0 for d in documents] == [True, True]


def test_run_delegates_to_load_data(tmp_path, engine) -> None:
    pdf = make_pdf(tmp_path / "run.pdf", [SHORT_TEXT])

    documents = OCRPDFReader(min_text_chars=200).run(pdf)

    assert len(documents) == 1
    assert engine.calls == 1


def test_pages_that_produce_no_text_are_skipped(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ocr_pdf_loader, "get_ocr_engine", lambda: None)
    pdf = make_pdf(tmp_path / "blank.pdf", ["", LONG_TEXT])

    documents = OCRPDFReader(min_text_chars=200).load_data(pdf)

    assert len(documents) == 1
    assert documents[0].metadata["page_label"] == "2"
