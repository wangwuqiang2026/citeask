"""Tests for ``tools/eval_retrieval.py``.

The harness runs the real application, which a unit test cannot do; everything that
decides a number — matching, ranking, per-category grouping, the exit code — is
pure and is covered here, so a change in the scoring cannot silently move the
metrics that are quoted in the README.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tools.eval_retrieval import (
    DEFAULT_CATEGORY,
    abstain_summary,
    build_retrievers,
    category_of,
    evaluate,
    exit_code,
    markdown_report,
    normalize,
    normalize_name,
    percentile,
    pick_doc_ids,
    summarize,
    summarize_by_category,
)


def make_doc(page, score, text="", name="细则.pdf"):
    return SimpleNamespace(
        doc_id=f"{name}-{page}-{score}",
        score=score,
        text=text,
        metadata={"file_name": name, "page_label": page},
    )


class FakeRetriever:
    def __init__(self, docs):
        self.docs = docs
        self.calls = []

    def run(self, question, doc_ids=None):
        self.calls.append((question, doc_ids))
        return list(self.docs)


# --------------------------------------------------------------------------- #
# matching
# --------------------------------------------------------------------------- #
def test_normalize_drops_every_whitespace_character():
    # OCR inserts line breaks anywhere, including inside a number
    assert normalize("满分\n为 100 分") == "满分为100分"


def test_normalize_name_ignores_punctuation_added_by_the_upload():
    # Gradio sanitizes `…（2025修订）.pdf` into `…2025修订.pdf`
    assert normalize_name("某学院积分细则（2025修订).pdf") == normalize_name(
        "某学院积分细则2025修订.pdf"
    )
    assert normalize_name(None) == ""


def test_unlabeled_questions_report_into_a_default_category():
    assert category_of({"question": "q"}) == DEFAULT_CATEGORY
    assert category_of({"category": "T2"}) == "T2"


def test_scope_selects_files_by_normalized_name():
    """The app's "search in file(s)" mode, needed to reproduce a per-corpus number.

    An index that also holds a ten-thousand-chunk spreadsheet dilutes the recall of a
    four-chunk PDF (measured: Hit@1 59.3% -> 33.3%), so a claim about the PDF has to
    be measurable under the scope the claim was made in.
    """
    rows = [
        ("id-1", "某学院积分细则（2025修订).pdf"),
        ("id-2", "中央机关招考简章.xls"),
    ]

    assert pick_doc_ids(rows, "") == ["id-1", "id-2"]
    assert pick_doc_ids(rows, "积分细则") == ["id-1"]
    assert pick_doc_ids(rows, "2025 修订") == ["id-1"]
    assert pick_doc_ids(rows, "简章") == ["id-2"]
    assert pick_doc_ids(rows, "不存在的文件") == []


# --------------------------------------------------------------------------- #
# ranking and scoring
# --------------------------------------------------------------------------- #
def test_evaluate_ranks_the_first_expected_page_and_counts_missing_facts():
    docs = [
        make_doc("1", 0.9, "满分 100 分"),
        make_doc("2", 0.8, "五个部分"),
    ]
    retriever = FakeRetriever(docs)
    questions = [
        {
            "id": "q1",
            "category": "T1",
            "question": "满分是多少",
            "expect_pages": ["2"],
            "expect_terms": ["五个部分", "不存在的词"],
        }
    ]

    results = evaluate(questions, [retriever], ["file-1"], "细则.pdf", k=5)

    assert retriever.calls == [("满分是多少", ["file-1"])]
    assert results[0]["rank"] == 1  # page 2 is the second result
    assert results[0]["mrr"] == 0.5
    assert results[0]["terms_ok"] is False
    assert results[0]["missing_terms"] == ["不存在的词"]
    assert results[0]["category"] == "T1"
    assert [r["page"] for r in results[0]["retrieved"]] == ["1", "2"]


def test_a_chunk_from_another_file_does_not_count_as_a_hit():
    docs = [make_doc("1", 0.9, name="别的文件.pdf"), make_doc("1", 0.5)]
    results = evaluate(
        [{"id": "q1", "question": "q", "expect_pages": ["1"]}],
        [FakeRetriever(docs)],
        ["file-1"],
        "细则.pdf",
        k=5,
    )

    assert results[0]["rank"] == 1


def test_summarize_computes_hit_rates_mrr_and_fact_coverage():
    results = [
        {"rank": 0, "mrr": 1.0, "terms_ok": True},
        {"rank": 2, "mrr": 1 / 3, "terms_ok": False},
        {"rank": None, "mrr": 0.0, "terms_ok": True},
    ]

    summary = summarize(results, k=5, corpus_chunks=8)

    assert summary["questions"] == 3
    assert summary["corpus_chunks"] == 8
    assert summary["hit_at_1"] == 1 / 3
    assert summary["hit_at_3"] == 2 / 3
    assert summary["hit_at_5"] == 2 / 3
    assert summary["facts"] == 2 / 3
    assert abs(summary["mrr"] - (1 + 1 / 3) / 3) < 1e-9


def test_summarize_of_an_empty_run_is_all_zero():
    summary = summarize([], k=5, corpus_chunks=0)

    assert summary["questions"] == 0
    assert summary["hit_at_1"] == 0.0
    assert summary["mrr"] == 0.0


# --------------------------------------------------------------------------- #
# categories
# --------------------------------------------------------------------------- #
def test_metrics_are_split_per_category():
    results = [
        {"category": "T1", "rank": 0, "mrr": 1.0, "terms_ok": True},
        {"category": "T1", "rank": None, "mrr": 0.0, "terms_ok": False},
        {"category": "T2", "rank": 3, "mrr": 0.25, "terms_ok": True},
    ]

    categories = summarize_by_category(results, k=5, corpus_chunks=8)

    assert list(categories) == ["T1", "T2"]  # stable order
    assert categories["T1"]["questions"] == 2
    assert categories["T1"]["hit_at_1"] == 0.5
    assert categories["T2"]["hit_at_1"] == 0.0
    assert categories["T2"]["mrr"] == 0.25


def test_an_unlabeled_set_yields_a_single_group():
    results = [
        {"rank": 0, "mrr": 1.0, "terms_ok": True},
        {"rank": 1, "mrr": 0.5, "terms_ok": True},
    ]

    categories = summarize_by_category(results, k=5, corpus_chunks=4)

    assert list(categories) == [DEFAULT_CATEGORY]
    assert categories[DEFAULT_CATEGORY]["questions"] == 2


# --------------------------------------------------------------------------- #
# reports and exit code
# --------------------------------------------------------------------------- #
def test_the_markdown_report_carries_the_category_table_only_when_split():
    results = [
        {
            "id": "q1",
            "category": "T1",
            "question": "a",
            "expect_pages": ["1"],
            "rank": 0,
            "mrr": 1.0,
            "terms_ok": True,
            "missing_terms": [],
        },
        {
            "id": "q2",
            "category": "T2",
            "question": "b",
            "expect_pages": ["2"],
            "rank": None,
            "mrr": 0.0,
            "terms_ok": False,
            "missing_terms": ["x"],
        },
    ]
    summary = summarize(results, k=5, corpus_chunks=4)

    split = markdown_report("t", summary, results, summarize_by_category(results, 5, 4))
    assert "#### 按类别" in split
    assert "| T1 |" in split and "| T2 |" in split
    assert "| 全部 |" in split

    single = markdown_report("t", summary, results, {DEFAULT_CATEGORY: summary})
    assert "#### 按类别" not in single
    assert "| # | 类别 | 问题 |" in single


def test_a_completed_run_without_a_gate_always_passes():
    summary = {"hit_at_1": 0.59}

    assert exit_code(summary, None) == 0
    assert exit_code(summary, 0.55) == 0
    assert exit_code(summary, 0.60) == 1


# --------------------------------------------------------------------------- #
# refusal gate (no-answer questions)
# --------------------------------------------------------------------------- #
def test_a_no_answer_question_is_scored_for_refusal_not_for_pages():
    docs = [make_doc("1", 0.30, "食堂开放时间")]  # unrelated weak match
    results = evaluate(
        [
            {
                "id": "n1",
                "category": "T4",
                "expect_answer": False,
                "question": "食堂几点开门？",
            }
        ],
        [FakeRetriever(docs)],
        ["file-1"],
        "细则.pdf",
        k=5,
        abstain_threshold=0.45,
    )

    result = results[0]
    assert result["abstain_case"] is True
    assert result["abstained"] is True
    assert result["top_score"] == 0.3
    assert result["rank"] is None
    assert result["terms_ok"] is False


def test_no_answer_questions_do_not_drag_the_retrieval_metrics():
    answerable = {
        "id": "q1",
        "question": "满分多少",
        "expect_pages": ["1"],
        "category": "T1",
    }
    no_answer = {"id": "n1", "question": "食堂几点", "expect_answer": False}
    docs = [make_doc("1", 0.9, "满分为 100 分")]

    results = evaluate(
        [answerable, no_answer], [FakeRetriever(docs)], ["file-1"], "细则.pdf", k=5
    )
    summary = summarize(results, k=5, corpus_chunks=4)

    assert summary["questions"] == 1  # the no-answer question is not counted
    assert summary["hit_at_1"] == 1.0


def test_abstain_summary_reports_both_sides_of_the_gate():
    results = [
        # no-answer questions
        {"abstain_case": True, "retrieved": [{"score": 0.30}]},
        {"abstain_case": True, "retrieved": [{"score": 0.60}]},
        # answerable questions, one of them keyword-only (-1 sentinel)
        {"abstain_case": False, "retrieved": [{"score": 0.70}]},
        {"abstain_case": False, "retrieved": [{"score": -1.0}]},
    ]

    summary = abstain_summary(results, threshold=0.45)

    assert summary["abstain_questions"] == 2
    assert summary["abstain_rate"] == 0.5  # 0.30 refused, 0.60 answered
    assert summary["false_reject_rate"] == 0.0  # 0.70 answered, sentinel not refused
    assert summary["threshold"] == 0.45


def test_abstain_summary_without_no_answer_questions_reports_none():
    summary = abstain_summary(
        [{"abstain_case": False, "retrieved": [{"score": 0.8}]}], threshold=0.45
    )

    assert summary["abstain_questions"] == 0
    assert summary["abstain_rate"] is None
    assert summary["false_reject_rate"] == 0.0


# --------------------------------------------------------------------------- #
# latency
# --------------------------------------------------------------------------- #
def test_percentile_interpolates_and_handles_degenerate_input():
    assert percentile([], 0.5) == 0.0
    assert percentile([7.0], 0.95) == 7.0
    assert percentile([1, 2, 3], 0.5) == 2.0
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
    assert percentile([10, 20], 0.95) == pytest.approx(19.5)


def test_summary_reports_latency_over_every_question():
    results = [
        {"rank": 0, "mrr": 1.0, "terms_ok": True, "elapsed_ms": 100.0},
        {"rank": 0, "mrr": 1.0, "terms_ok": True, "elapsed_ms": 300.0},
        # a no-answer question still spends retrieval time
        {"abstain_case": True, "retrieved": [], "elapsed_ms": 200.0},
    ]

    summary = summarize(results, k=5, corpus_chunks=4)

    assert summary["questions"] == 2  # the no-answer question is not scored
    assert summary["latency_p50_ms"] == 200.0
    assert summary["latency_p95_ms"] == pytest.approx(290.0)


# --------------------------------------------------------------------------- #
# reranker A/B switch
# --------------------------------------------------------------------------- #
def test_build_retrievers_pins_the_reranker_for_an_ab_run():
    seen = {}

    class FakePipeline:
        @classmethod
        def get_pipeline(cls, user_settings, index_settings, selected):
            seen["use_reranking"] = user_settings.get("use_reranking")
            seen["selected"] = selected
            return SimpleNamespace()

    index = SimpleNamespace(
        id=1,
        config={},
        _retriever_pipeline_cls=[FakePipeline],
        _resources={"Source": object, "Index": object},
        _vs=object(),
        _docstore=object(),
        _fs_path=".",
    )

    build_retrievers(
        index, {"index.options.1.use_reranking": True}, "u", ["d"], rerank=False
    )
    assert seen["use_reranking"] is False
    assert seen["selected"] == ["d"]

    build_retrievers(
        index, {"index.options.1.use_reranking": False}, "u", ["d"], rerank=True
    )
    assert seen["use_reranking"] is True

    # not pinned: the app setting is what the run uses
    build_retrievers(index, {"index.options.1.use_reranking": True}, "u", ["d"])
    assert seen["use_reranking"] is True
