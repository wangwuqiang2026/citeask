"""Tests for the Chinese full-text index of the LanceDB document store.

The index used to be built with ``en_stem``, which tokenizes on whitespace: a Chinese
question is one giant token, so the full-text channel returned nothing for every real
question and the retriever silently fell back to vector-only search — where a dense
table row scores far below a natural-language question and is never retrieved
(MODIFICATIONS §5.15). The n-gram tokenizer is what makes an exact-name lookup work.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

from kotaemon.base import Document
from kotaemon.storages.docstores.lancedb import (
    FTS_TOKENIZER_SIGNATURE,
    LanceDBDocumentStore,
)

DOCUMENTS = [
    Document(
        text="某班级,24405010001,李同学,8,24,2025上半年8学时",
        metadata={"file_name": "社会实践完成情况表.xlsx"},
    ),
    Document(
        text="某学院入党积极分子积分细则 第一条 积分由五个部分组成",
        metadata={"file_name": "积分细则.pdf"},
    ),
]


@pytest.fixture
def workdir():
    """Scratch directory (Path.mkdir, not mkdtemp: 0o700 dirs are not writable here)."""
    path = Path(tempfile.gettempdir()) / f"fts-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def store(workdir):
    pytest.importorskip("lancedb")
    store = LanceDBDocumentStore(
        path=str(workdir / "docstore"), collection_name="index_test"
    )
    store.add(DOCUMENTS, ids=["a", "b"])
    return store


def test_a_chinese_question_matches_the_row(store):
    """The tokenizer must split Chinese into grams, so a *question* matches a row."""
    docs = store.query("李同学的社会实践完成得怎么样", top_k=5)

    assert docs, "the full-text channel returned nothing for a Chinese question"
    assert any("李同学" in doc.text for doc in docs)


def test_an_exact_name_matches(store):
    docs = store.query("李同学", top_k=5)

    assert [doc.doc_id for doc in docs][:1] == ["a"]


def test_a_scoped_query_still_finds_the_row(store):
    """The retriever always passes a ``scope`` (the selected files' chunk ids).

    With the filter pushed down *before* the full-text match (``prefilter=True``, the
    upstream value) LanceDB returned **zero** rows for a small scope: the keyword
    channel was empty exactly when the selection was small, while a huge scope happened
    to work, which is why the bug survived the corpus-wide checks
    (MODIFICATIONS §5.19). The filter has to be applied after the match.
    """
    assert [doc.doc_id for doc in store.query("李同学", top_k=5, doc_ids=["a"])] == ["a"]
    assert [doc.doc_id for doc in store.query("李同学", top_k=5, doc_ids=["a", "b"])][
        :1
    ] == ["a"]
    assert store.query("李同学", top_k=5, doc_ids=["b"]) == []


def test_the_index_timestamp_is_recorded(store):
    """A marker records which tokenizer built the index, so it is rebuilt once."""
    marker = Path(store._fts_marker_path)

    assert marker.exists()
    assert marker.read_text(encoding="utf-8").strip() == FTS_TOKENIZER_SIGNATURE
    assert store.ensure_fts_index() is False  # already current


def test_an_index_built_by_an_older_version_is_rebuilt(store, workdir):
    """Deleting the marker simulates a corpus indexed with the old tokenizer."""
    Path(store._fts_marker_path).unlink()

    assert store.ensure_fts_index() is True
    docs = store.query("李同学的社会实践完成得怎么样", top_k=5)
    assert any("李同学" in doc.text for doc in docs)


def test_an_empty_document_set_does_not_crash_the_query(workdir):
    pytest.importorskip("lancedb")
    empty = LanceDBDocumentStore(
        path=str(workdir / "empty"), collection_name="index_empty"
    )

    assert empty.query("李同学", top_k=3) == []
    assert empty.ensure_fts_index() is False
