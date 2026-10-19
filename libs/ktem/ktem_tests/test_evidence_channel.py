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
    assert items[0]["vector_score"] == 0.2
    assert items[0]["spans"] == [{"start": 0, "end": 2, "idx": 1}]
    assert items[1]["cited"] is False
    assert items[1]["spans"] == []

    # every record must survive JSON serialisation (the SSE layer dumps it)
    import json

    json.dumps(items)


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
