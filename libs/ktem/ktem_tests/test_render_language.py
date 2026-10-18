"""Tests for the language detection used when rendering a citation preview.

``fast_langdetect.detect`` returns a **list** of results. The preview code used to index
it with ``["lang"]``, which raised ``TypeError: list indices must be integers or slices,
not str`` on every citation and was swallowed by a bare ``except`` — the language-aware
highlighting never ran and each answer printed a few error lines (MODIFICATIONS §5.19).
"""

from __future__ import annotations

from ktem.utils import render


def test_a_list_result_is_unwrapped(monkeypatch):
    monkeypatch.setattr(render, "detect", lambda text: [{"lang": "zh", "score": 0.9}])

    assert render.detect_language("积分细则") == "zh"


def test_a_dict_result_still_works(monkeypatch):
    monkeypatch.setattr(render, "detect", lambda text: {"lang": "en", "score": 0.8})

    assert render.detect_language("admission") == "en"


def test_an_empty_result_is_not_an_error(monkeypatch):
    monkeypatch.setattr(render, "detect", lambda text: [])

    assert render.detect_language("") is None


def test_a_failing_detector_returns_none(monkeypatch):
    def boom(text):
        raise RuntimeError("model missing")

    monkeypatch.setattr(render, "detect", boom)

    assert render.detect_language("text") is None


def test_a_citation_preview_keeps_working_with_the_real_detector():
    """The real detector returns a list; the preview must still produce a link."""
    from kotaemon.base import RetrievedDocument

    doc = RetrievedDocument(
        text="某学院入党积极分子积分细则 第一条",
        metadata={
            "file_type": "application/pdf",
            "page_label": 1,
            "file_path": __file__,
        },
    )

    html = render.Render.preview("<p>正文</p>", doc)

    assert "pdf-link" in html
    assert "data-search=" in html
