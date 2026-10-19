"""Tests for the relevance score shown in the evidence ("信息面板") panel.

Every chunk used to be rendered with ``[得分: 0.0]`` / ``相关性分数: 0.0``: the panel
read ``llm_trulens_score`` for the header and ``llm_trulens_score``/``reranking_score``
for the label, while the configured reranker (the local lexical one) writes
``rerank_score`` and the LLM judge is off by default. A retrieval miss therefore looked
exactly like an empty store in the UI, and the panel could not be used to tell which
chunk ranked where (MODIFICATIONS §5.21).
"""

from __future__ import annotations

from ktem.utils.render import (
    Render,
    has_rerank_score,
    relevance_score_of,
    reranking_score_of,
)
from kotaemon.base import RetrievedDocument


def panel_doc(score=0.44, **metadata):
    base = {"file_id": "grades", "file_name": "示例班级学年综测汇总表.xlsx"}
    base.update(metadata)
    return RetrievedDocument(
        text="24405010135 张同学 75.45 84.27", metadata=base, score=score
    )


def header_of(doc):
    """The collapsed header, which is what the panel shows before expanding a chunk."""
    return Render.collapsible_with_header_score(doc).split("</summary>")[0]


def test_the_local_reranker_score_is_shown():
    doc = panel_doc(rerank_score=0.35)

    assert reranking_score_of(doc) == 0.35
    assert relevance_score_of(doc) == 0.35
    assert "0.35" in header_of(doc)


def test_a_provider_reranker_score_wins_over_the_lexical_one():
    doc = panel_doc(reranking_score=0.7, rerank_score=0.35)

    assert reranking_score_of(doc) == 0.7
    assert relevance_score_of(doc) == 0.7


def test_the_llm_judge_wins_when_it_ran():
    doc = panel_doc(llm_trulens_score=8.0, rerank_score=0.35)

    assert relevance_score_of(doc) == 8.0
    assert "8.0" in header_of(doc)


def test_a_vector_match_is_better_than_a_blank_panel():
    """No reranker, no judge: the similarity is still a signal, so show it."""
    doc = panel_doc(0.44)

    assert relevance_score_of(doc) == 0.44
    assert "0.44" in header_of(doc)


def test_a_reranker_that_scored_zero_is_shown_as_zero():
    """0.0 is the reranker's verdict, not "no score".

    Falling back to the vector similarity here mixed two scales: a chunk the reranker
    had rejected showed 0.31 while the chunk that matched the question showed 0.29, so
    the panel made relevant and unrelated chunks look the same (MODIFICATIONS §5.23).
    """
    doc = panel_doc(0.31, rerank_score=0.0)

    assert has_rerank_score(doc) is True
    assert relevance_score_of(doc) == 0.0
    assert "0.31" not in header_of(doc)


def test_a_full_text_hit_has_no_similarity_to_show():
    """Keyword hits carry ``-1``; reporting "-1.0" would read as a broken score."""
    doc = panel_doc(-1.0)

    assert relevance_score_of(doc) == 0.0
    assert "-1" not in header_of(doc)


def test_malformed_scores_do_not_break_the_panel():
    doc = RetrievedDocument(
        text="row",
        metadata={"file_id": "x", "rerank_score": "not-a-number"},
        score=0.0,
    )

    assert reranking_score_of(doc) == 0.0
    assert relevance_score_of(doc) == 0.0
