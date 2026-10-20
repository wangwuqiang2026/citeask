"""The structured evidence channel added for the web UI (MODIFICATIONS §5.25).

The classic panel keeps rendering HTML; the web UI needs the same evidence as
data. These tests pin the shape and the ordering without touching an LLM.
"""

from __future__ import annotations

from types import SimpleNamespace

from kotaemon.base import Document, RetrievedDocument

from ktem.reasoning.simple import FullQAPipeline


class FakeAnsweringPipeline:
    def __init__(self, spans: dict):
        self._spans = spans

    def match_evidence_with_context(self, answer, docs):
        return self._spans


def make_doc(name: str, text: str, score: float, **metadata) -> RetrievedDocument:
    base = {"file_id": f"file-{name}", "file_name": name, "page_label": 1}
    base.update(metadata)
    return RetrievedDocument(text=text, metadata=base, score=score)


def test_new_channels_are_accepted():
    assert Document(channel="evidence", content=[]).channel == "evidence"
    assert Document(channel="mindmap", content="- a").channel == "mindmap"


def test_evidence_records_are_json_friendly_and_cited_first():
    first = make_doc("无关.pdf", "无关内容", 0.31)
    cited = make_doc("制度.pdf", "制度正文", 0.20, rerank_score=0.90)
    third = make_doc("其他.pdf", "其他内容", 0.12)

    spans = {cited.doc_id: [{"start": 0, "end": 2, "idx": 1}]}
    service = SimpleNamespace(answering_pipeline=FakeAnsweringPipeline(spans))

    items = FullQAPipeline.structured_evidence(service, SimpleNamespace(), [first, cited, third])

    assert [item["file_name"] for item in items] == ["制度.pdf", "无关.pdf", "其他.pdf"]
    assert items[0]["cited"] is True
    assert items[0]["score"] == 0.9, "the reranker score is the displayed relevance"
    assert items[0]["rerank_score"] == 0.9
    assert items[0]["vector_score"] == 0.2
    assert items[0]["spans"] == [{"start": 0, "end": 2, "idx": 1}]
    assert items[1]["cited"] is False
    assert items[1]["spans"] == []
    # no reranker ran on these chunks: the score is missing, not 0.0. The panel must
    # be able to tell "never scored" from "the reranker said zero" (MODIFICATIONS §5.32)
    assert items[1]["rerank_score"] is None
    assert items[2]["rerank_score"] is None

    # every record must survive JSON serialisation (the SSE layer dumps it)
    import json

    json.dumps(items)


def test_entity_row_chunks_are_flagged_and_carry_no_lexical_score():
    """The row lookup adds chunks after reranking; they are cited-relevant evidence.

    A promoted row has ``score = NO_SIMILARITY`` and no ``rerank_score`` metadata, so
    the payload used to show ``0.0`` for the chunk that actually names the queried
    person (MODIFICATIONS §5.32).
    """
    promoted = make_doc("实践表.xlsx", "…王务强 32…", -1.0, entity_row=True)
    regular = make_doc("制度.pdf", "制度正文", 0.35, rerank_score=0.0)

    spans = {promoted.doc_id: [{"start": 0, "end": 2, "idx": None}]}
    service = SimpleNamespace(answering_pipeline=FakeAnsweringPipeline(spans))
    items = FullQAPipeline.structured_evidence(
        service, SimpleNamespace(), [regular, promoted]
    )

    assert items[0]["cited"] is True
    assert items[0]["entity_row"] is True
    assert items[0]["rerank_score"] is None, "a missing score is not a zero score"
    assert items[1]["entity_row"] is False
    assert items[1]["rerank_score"] == 0.0, "a reranker verdict of zero stays zero"


def test_evidence_survives_a_failing_span_matcher():
    def boom(answer, docs):
        raise RuntimeError("judge unavailable")

    service = SimpleNamespace(answering_pipeline=SimpleNamespace(
        match_evidence_with_context=boom
    ))
    items = FullQAPipeline.structured_evidence(
        service, SimpleNamespace(), [make_doc("a.pdf", "a", 0.5)]
    )

    assert len(items) == 1
    assert items[0]["cited"] is False
    assert items[0]["score"] == 0.5
