"""Tests for ``tools/doctor.py``.

The check itself needs the application; every judgement it makes — "is this file
retrievable", "is this warning a failure", "does a completed run pass" — is pure and
is pinned here, so the self-check cannot quietly start passing everything.
"""

from __future__ import annotations

from pathlib import Path

from tools.doctor import (
    FAIL,
    OK,
    WARN,
    chunk_size_finding,
    effective_chunk_size,
    empty_chunk_finding,
    exit_code,
    file_finding,
    finding,
    load_smoke_questions,
    render_table,
    reranker_finding,
    smoke_finding,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# per-file check
# --------------------------------------------------------------------------- #
def source_row(**kwargs):
    row = {
        "name": "细则.pdf",
        "note": {"tokens": 2562, "loader": "OCRPDFReader"},
        "documents": 4,
        "vectors": 4,
    }
    row.update(kwargs)
    return row


def test_a_healthy_file_is_ok():
    result = file_finding(source_row())

    assert result["status"] == OK
    assert "4 块 / 4 向量" in result["detail"]


def test_a_file_without_vectors_fails_and_says_why():
    """The §2.10 shape: listed, looks indexed, answers nothing."""
    result = file_finding(
        source_row(
            documents=10237,
            vectors=0,
            note={"error": "Missing optional dependency 'xlrd'"},
        )
    )

    assert result["status"] == FAIL
    assert "0 个向量块" in result["detail"]
    assert "xlrd" in result["detail"]


def test_a_file_without_vectors_and_without_an_error_is_still_a_failure():
    result = file_finding(source_row(documents=0, vectors=0, note={}))

    assert result["status"] == FAIL
    assert "indexing never finished" in result["detail"]


def test_a_file_whose_last_indexing_errored_is_a_warning_when_vectors_exist():
    result = file_finding(source_row(note={"error": "rate limited", "loader": "x"}))

    assert result["status"] == WARN
    assert "rate limited" in result["detail"]


def test_a_file_without_a_loader_note_is_a_warning():
    result = file_finding(source_row(note={"tokens": 10}))

    assert result["status"] == WARN
    assert "读取器" in result["detail"]


# --------------------------------------------------------------------------- #
# chunk text
# --------------------------------------------------------------------------- #
def test_empty_chunks_are_judged_by_ratio():
    assert empty_chunk_finding(0, 0)["status"] == WARN
    assert empty_chunk_finding(100, 0)["status"] == OK
    assert empty_chunk_finding(100, 3)["status"] == WARN
    assert empty_chunk_finding(100, 30)["status"] == FAIL


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #
def test_a_reranker_without_a_key_is_a_warning():
    """Configured but inert: the list comes back unchanged (ROADMAP B2)."""
    assert reranker_finding("cohere", has_key=False, enabled=False)["status"] == OK
    result = reranker_finding("cohere", has_key=False, enabled=True)
    assert result["status"] == WARN
    assert "没有 API key" in result["detail"]
    assert reranker_finding("cohere", has_key=True, enabled=True)["status"] == OK


def test_page_level_chunking_is_flagged():
    assert chunk_size_finding(0)["status"] == WARN
    assert chunk_size_finding(512)["status"] == OK
    assert "token" in chunk_size_finding(512)["detail"]


def test_the_effective_chunk_size_falls_back_to_the_pipeline_default():
    """The index stores 0 unless overridden; the default lives in flowsettings.

    Reading only the index value reported "按页成块" while the pipeline was already
    splitting by token — a stale warning is as misleading as a missing one.
    """
    assert effective_chunk_size(0, 512) == 512
    assert effective_chunk_size(256, 512) == 256  # per-index override wins
    assert effective_chunk_size(0, 0) == 0
    assert effective_chunk_size(None, None) == 0


# --------------------------------------------------------------------------- #
# retrieval smoke
# --------------------------------------------------------------------------- #
def test_smoke_fails_when_a_question_returns_nothing():
    rows = [
        {"question": "a", "retrieved": 5, "page_hit": True},
        {"question": "b", "retrieved": 0, "page_hit": False},
    ]

    result = smoke_finding(rows)

    assert result["status"] == FAIL
    assert "1/2 题有召回" in result["detail"]


def test_smoke_is_ok_when_every_question_returns_something():
    rows = [
        {"question": "a", "retrieved": 5, "page_hit": True},
        {"question": "b", "retrieved": 3, "page_hit": False},
    ]

    result = smoke_finding(rows)

    assert result["status"] == OK
    assert "1/2 题命中期望页" in result["detail"]


def test_smoke_is_skipped_not_ok_when_nothing_ran():
    assert smoke_finding([])["status"] == WARN


def test_smoke_questions_are_read_from_the_committed_set():
    questions = load_smoke_questions(
        REPO_ROOT / "tools" / "eval" / "zh-points-rules.json", limit=3
    )

    assert len(questions) == 3
    assert questions[0]["_corpus"]  # the corpus name is carried for page matching
    assert questions[0]["question"]


def test_missing_eval_set_yields_no_smoke_questions():
    assert load_smoke_questions(REPO_ROOT / "tools" / "eval" / "nope.json") == []


# --------------------------------------------------------------------------- #
# exit codes and rendering
# --------------------------------------------------------------------------- #
def test_exit_code_follows_the_worst_finding():
    assert exit_code([finding("a", OK)]) == 0
    assert exit_code([finding("a", OK), finding("b", WARN)]) == 0
    assert exit_code([finding("a", WARN), finding("b", FAIL)]) == 1
    assert exit_code([]) == 0


def test_strict_turns_warnings_into_a_failure():
    findings = [finding("a", WARN)]

    assert exit_code(findings) == 0
    assert exit_code(findings, strict=True) == 1


def test_the_table_marks_statuses_and_escapes_pipes():
    table = render_table(
        [finding("文件 a", OK, "4 块"), finding("文件 b", FAIL, "0 块 | 无向量")]
    )

    assert "| OK |" in table
    assert "| ❌ FAIL |" in table
    assert "0 块 \\| 无向量" in table
