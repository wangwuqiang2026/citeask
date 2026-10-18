"""Tests for the committed retrieval fixture (``tools/eval/fixtures``).

The point of the fixture is that a **fresh clone** can reproduce a retrieval number
without any private corpus: the file, the question set and the numbers must all live in
the repository. These tests pin the part that can drift silently - the eval set referring
to pages/terms the fixture does not contain - so the committed pair stays consistent.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
EVAL_JSON = REPO / "tools" / "eval" / "fixture-points.json"
FIXTURE = REPO / "tools" / "eval" / "fixtures" / "points-fixture.pptx"


def normalize(text: str) -> str:
    """Same rule as the harness: every whitespace character is dropped."""
    return "".join(str(text or "").split())


@pytest.fixture(scope="module")
def slides() -> dict[str, str]:
    """``{page_label: text}`` as the app's PPTX loader sees the fixture."""
    pytest.importorskip("pptx")
    from kotaemon.loaders.pptx_loader import PptxReader

    documents = PptxReader().load_data(file_path=str(FIXTURE))
    return {str(doc.metadata.get("page_label")): normalize(doc.text) for doc in documents}


@pytest.fixture(scope="module")
def eval_set() -> dict:
    return json.loads(EVAL_JSON.read_text(encoding="utf-8"))


def test_the_fixture_is_committed_and_reads_as_five_pages(slides):
    assert FIXTURE.is_file(), "the fixture must be committed, not generated at run time"
    assert sorted(slides, key=int) == ["1", "2", "3", "4", "5"]


def test_the_eval_set_points_at_the_fixture(eval_set):
    assert eval_set["corpus"] == FIXTURE.name


def test_every_expected_page_exists(eval_set, slides):
    pages = {p for q in eval_set["questions"] for p in q.get("expect_pages", [])}

    assert pages, "the set must check at least one page"
    assert pages <= set(slides), f"unknown pages: {sorted(pages - set(slides))}"


def test_every_expected_term_is_really_in_the_fixture(eval_set, slides):
    """A typo here would silently turn a Hit into a miss forever."""
    missing = []
    for question in eval_set["questions"]:
        text = "".join(slides.get(str(page), "") for page in question.get("expect_pages", []))
        for raw in question.get("expect_terms", []):
            if normalize(raw) not in text:
                missing.append((question["id"], raw))

    assert missing == []


def test_the_unanswerable_question_is_absent_from_the_fixture(eval_set, slides):
    """The no-answer entry is only meaningful if the corpus really cannot answer it."""
    corpus = "".join(slides.values())
    for term in ("食堂", "开门"):
        assert term not in corpus


def test_the_question_ids_are_unique(eval_set):
    ids = [question["id"] for question in eval_set["questions"]]

    assert len(ids) == len(set(ids))


def test_the_generator_produces_the_same_text(tmp_path):
    """Regenerating the fixture must not change what the eval set can match."""
    from tools.eval.make_fixture import build

    regenerated = build(tmp_path / "points-fixture.pptx")
    from kotaemon.loaders.pptx_loader import PptxReader

    text = normalize("".join(doc.text for doc in PptxReader().load_data(file_path=str(regenerated))))

    assert "五个部分" in text
    assert re.search(r"优秀,10\s*分", text)
