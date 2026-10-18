"""Tests for the per-file retrieval pass (``ktem.utils.retrieval``).

A single vector query ranks across the whole index, so a 10k-chunk spreadsheet can take
every context slot while the 6-chunk table that actually answers the question never
appears (MODIFICATIONS §5.13). The fix is a post-retrieval pass; its contract is pinned
here.
"""

from __future__ import annotations

from types import SimpleNamespace

from ktem.utils.retrieval import absent_source_ids, diversify_by_source, source_key
from kotaemon.indices.vectorindex import (
    limit_keyword_only,
    similarity_documents_first,
)


def doc(file_id, rank, file_name=None):
    metadata = {"file_id": file_id}
    if file_name:
        metadata["file_name"] = file_name
    return SimpleNamespace(
        metadata=metadata, text=f"{file_id}-{rank}", score=1.0 / rank
    )


def test_a_single_file_keeps_the_plain_ranking():
    docs = [doc("a", 1), doc("a", 2), doc("a", 3)]

    picked = diversify_by_source(docs, top_k=2)

    assert picked == docs[:2]


def test_the_best_chunk_of_every_file_comes_before_any_second_chunk():
    """The large file ranks 1-4, the small one 5: the small file still gets a slot."""
    docs = [doc("big", 1), doc("big", 2), doc("big", 3), doc("small", 4)]

    picked = diversify_by_source(docs, top_k=3)

    assert [d.metadata["file_id"] for d in picked] == ["big", "small", "big"]


def test_files_are_visited_in_the_order_of_their_best_chunk():
    docs = [doc("second", 1), doc("first", 2)]

    picked = diversify_by_source(docs, top_k=2)

    assert [d.metadata["file_id"] for d in picked] == ["second", "first"]


def test_per_source_cap_limits_how_much_one_file_contributes():
    docs = [doc("a", 1), doc("a", 2), doc("a", 3), doc("b", 4)]

    picked = diversify_by_source(docs, top_k=4, per_source_k=1)

    assert [d.text for d in picked] == ["a-1", "b-4"]


def test_documents_without_a_file_id_are_one_group():
    plain = [
        SimpleNamespace(metadata={}, text="x"),
        SimpleNamespace(metadata=None, text="y"),
    ]

    picked = diversify_by_source(plain, top_k=1)

    assert [d.text for d in picked] == ["x"]


def test_a_zero_budget_returns_nothing():
    assert diversify_by_source([doc("a", 1)], top_k=0) == []


def test_asking_for_more_than_available_returns_everything():
    docs = [doc("a", 1), doc("b", 2)]

    assert diversify_by_source(docs, top_k=10) == docs


def test_the_grouping_key_prefers_file_id_then_file_name():
    assert source_key(doc("id-1", 1)) == "id-1"
    assert source_key(SimpleNamespace(metadata={"file_name": "t.xlsx"})) == "t.xlsx"
    assert source_key(SimpleNamespace(metadata={})) == ""


def test_absent_files_are_the_ones_worth_a_second_query():
    """Only files with no chunk in the context cost an extra query."""
    docs = [doc("big", 1), doc("big", 2)]

    assert absent_source_ids(docs, ["big", "small", "other"]) == ["small", "other"]


def test_no_absent_files_when_every_file_is_represented():
    docs = [doc("a", 1), doc("b", 2)]

    assert absent_source_ids(docs, ["b", "a"]) == []


def test_absent_files_reports_nothing_for_an_empty_selection():
    assert absent_source_ids([doc("a", 1)], []) == []


# --------------------------------------------------------------------------- #
# keyword slots (the refusal gate needs a similarity to judge)
# --------------------------------------------------------------------------- #
def keyword_doc(rank):
    return SimpleNamespace(metadata={"file_id": "table"}, text=f"keyword-{rank}", score=-1.0)


def scored_doc(rank, score):
    return SimpleNamespace(metadata={"file_id": "prose"}, text=f"vector-{rank}", score=score)


def test_keyword_hits_may_not_take_every_slot():
    """A working full-text index can flood the list with score-less hits; the refusal
    gate then has no similarity to judge and answers everything (§5.15)."""
    documents = [keyword_doc(index) for index in range(6)] + [
        scored_doc(index, 0.4) for index in range(4)
    ]

    kept = limit_keyword_only(documents, budget=3)

    assert sum(1 for item in kept if item.score < 0) == 3
    assert sum(1 for item in kept if item.score > 0) == 4


def test_a_keyword_budget_of_one_still_keeps_one_hit():
    documents = [keyword_doc(1), scored_doc(1, 0.5)]

    kept = limit_keyword_only(documents, budget=1)

    assert [item.text for item in kept] == ["keyword-1", "vector-1"]


# --------------------------------------------------------------------------- #
# keyword hits must not outrank a similarity match (§5.19)
# --------------------------------------------------------------------------- #
def test_keyword_hits_go_after_every_similarity_match():
    """Ordering them first pushed the best chunks out of the context.

    Once the full-text index started returning hits for a *scoped* query, the list was
    ``[keyword..., vector...]``: the reranker then floated a keyword hit (high question
    coverage, no similarity) to the front, ``diversify_by_source`` took it as its file's
    best chunk, and a 0.62 chunk was dropped for a hit scored ``-1`` — 16 of the 27
    answerable questions were refused that way (MODIFICATIONS §5.19).
    """
    documents = [
        keyword_doc(1),
        scored_doc(1, 0.62),
        keyword_doc(2),
        scored_doc(2, 0.48),
    ]

    ordered = similarity_documents_first(documents)

    assert [item.text for item in ordered] == [
        "vector-1",
        "vector-2",
        "keyword-1",
        "keyword-2",
    ]


def test_a_list_without_keyword_hits_keeps_its_order():
    documents = [scored_doc(index, 0.5) for index in range(3)]

    assert similarity_documents_first(documents) == documents


def test_a_broken_score_is_treated_as_a_similarity_match():
    """A malformed score must not crash the ordering (and must not demote the document)."""
    documents = [
        SimpleNamespace(metadata={}, text="broken", score=None),
        keyword_doc(1),
    ]

    assert [item.text for item in similarity_documents_first(documents)] == [
        "broken",
        "keyword-1",
    ]
