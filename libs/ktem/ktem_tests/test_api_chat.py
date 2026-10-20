"""The SSE chat endpoint, driven by a fake pipeline (no model calls)."""

from __future__ import annotations

import pytest
from kotaemon.base import Document

from ktem.services.chat import ChatService
from ktem.services.conversations import ConversationService
from ktem.services.settings import SettingsService

EVENT_NAMES = (
    "event: start",
    "event: token",
    "event: evidence",
    "event: done",
)


class FakePipeline:
    """Streams two tokens, one evidence record, and a mindmap."""

    def stream(self, message, conv_id, history):
        yield Document(channel="chat", content="你好")
        yield Document(channel="chat", content="，世界")
        yield Document(
            channel="evidence",
            content=[
                {
                    "id": "doc-1",
                    "file_id": "file-1",
                    "file_name": "制度.pdf",
                    "page": 3,
                    "type": "text",
                    "score": 0.82,
                    "vector_score": 0.5,
                    "rerank_score": 0.82,
                    "llm_score": 0.0,
                    "text": "制度正文",
                    "file_path": "",
                    "cited": True,
                    "spans": [{"start": 0, "end": 4, "idx": 1}],
                }
            ],
        )
        yield Document(channel="mindmap", content="- 根\n  - 子")
        return Document(text="你好，世界")


def _patch_pipeline(monkeypatch):
    monkeypatch.setattr(
        ChatService, "build_pipeline", lambda self, *args, **kwargs: (FakePipeline(), {}, "simple")
    )
    monkeypatch.setattr(
        ChatService,
        "_suggest_name",
        staticmethod(lambda pairs, language="en": None),
    )
    monkeypatch.setattr(ChatService, "_suggestions", lambda self, *args, **kwargs: [])


def _read_stream(client, conversation_id, body):
    chunks = []
    with client.stream(
        "POST", f"/api/v1/conversations/{conversation_id}/messages", json=body
    ) as response:
        assert response.status_code == 200
        for chunk in response.iter_text():
            chunks.append(chunk)
    return "".join(chunks)


def test_stream_events_and_persistence(monkeypatch, logged_in):
    _patch_pipeline(monkeypatch)
    conversation_id = logged_in.post("/api/v1/conversations", json={}).json()["id"]

    body = _read_stream(logged_in, conversation_id, {"message": "制度写了什么？"})
    for name in EVENT_NAMES:
        assert name in body, f"{name} missing from the stream"
    assert "event: mindmap" in body
    assert "你好" in body and "，世界" in body

    detail = logged_in.get(f"/api/v1/conversations/{conversation_id}").json()
    assert [item["role"] for item in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][0]["content"] == "制度写了什么？"
    assert detail["messages"][1]["content"] == "你好，世界"
    assert detail["evidence_history"][0][0]["file_name"] == "制度.pdf"
    assert detail["evidence_history"][0][0]["cited"] is True

    logged_in.delete(f"/api/v1/conversations/{conversation_id}")


def test_regenerate_replaces_the_last_answer(monkeypatch, logged_in):
    _patch_pipeline(monkeypatch)
    conversation_id = logged_in.post("/api/v1/conversations", json={}).json()["id"]

    _read_stream(logged_in, conversation_id, {"message": "第一问"})
    _read_stream(logged_in, conversation_id, {"message": "", "regenerate": True})

    detail = logged_in.get(f"/api/v1/conversations/{conversation_id}").json()
    assert len(detail["messages"]) == 2, "regenerate must replace, not append"
    assert detail["messages"][0]["content"] == "第一问"
    assert detail["evidence_history"][0][0]["file_name"] == "制度.pdf"

    logged_in.delete(f"/api/v1/conversations/{conversation_id}")


def test_stream_reports_pipeline_errors(monkeypatch, logged_in):
    def boom(self, *args, **kwargs):
        raise RuntimeError("模型未配置")

    monkeypatch.setattr(ChatService, "build_pipeline", boom)
    conversation_id = logged_in.post("/api/v1/conversations", json={}).json()["id"]

    body = _read_stream(logged_in, conversation_id, {"message": "hi"})
    assert "event: error" in body
    assert "模型未配置" in body

    detail = logged_in.get(f"/api/v1/conversations/{conversation_id}").json()
    assert detail["messages"] == [], "a failed turn must not be persisted"
    logged_in.delete(f"/api/v1/conversations/{conversation_id}")


def test_a_cancelled_turn_is_not_persisted(monkeypatch, application):
    """Pressing "stop" must end the turn without saving it.

    The worker runs the pipeline in a thread and keeps producing after the client
    disconnects; without an explicit cancellation signal it also persisted the
    abandoned half-answer. The stream must end silently: no ``done``, no saved
    turn, and no follow-up events (title/suggestions).
    """
    import threading

    cancel = threading.Event()

    class CancellingPipeline:
        """Streams one token, then the user presses stop."""

        def stream(self, message, conv_id, history):
            yield Document(channel="chat", content="第一段")
            cancel.set()
            yield Document(channel="chat", content="不该出现")

    monkeypatch.setattr(
        ChatService,
        "build_pipeline",
        lambda self, *args, **kwargs: (CancellingPipeline(), {}, "simple"),
    )
    monkeypatch.setattr(ChatService, "_scoped_ids", lambda self, *args, **kwargs: [])
    monkeypatch.setattr(ChatService, "_suggest_name", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(ChatService, "_suggestions", lambda self, *a, **k: [])
    monkeypatch.setattr(
        ConversationService,
        "history_for_pipeline",
        lambda self, *args, **kwargs: ([], {"app": {"regen": False}}),
    )
    monkeypatch.setattr(SettingsService, "load", lambda self, *args, **kwargs: {})

    persisted = []
    monkeypatch.setattr(
        ConversationService,
        "persist_turn",
        lambda self, **kwargs: persisted.append(kwargs),
    )

    service = ChatService(application)
    events = list(
        service.stream(
            conversation_id="conv-cancel",
            user={"id": 1},
            message="hi",
            cancel=cancel,
        )
    )
    names = [event["event"] for event in events]
    assert "done" not in names, "a cancelled turn must not report completion"
    assert "token" in names, "the token produced before the stop should still stream"
    assert persisted == [], "a cancelled turn must not be written to the database"



def test_suggest_name_uses_answer_language(monkeypatch):
    from ktem.services import chat as chat_module

    seen = {}

    class FakeTitlePipeline:
        lang = "English"

        def __call__(self, pairs):
            seen["lang"] = self.lang
            return Document(text='"中文标题"')

    monkeypatch.setattr(chat_module, "SuggestConvNamePipeline", FakeTitlePipeline)

    assert ChatService._suggest_name([["问", "答"]], "zh") == "中文标题"
    assert seen["lang"] == "Chinese"


def test_build_pipeline_without_any_model_says_what_to_do(application, monkeypatch):
    """A fresh install with no configured provider must not surface a raw error.

    Presets with placeholder credentials are no longer seeded (§5.34), so the pool
    can legitimately be empty; the chat should point the user at the resources page
    instead of failing with upstream's "No models in pool".
    """
    from ktem.llms.manager import llms

    monkeypatch.setattr(llms, "options", lambda: {})
    service = ChatService(application)

    with pytest.raises(ValueError) as excinfo:
        service.build_pipeline(
            settings={"reasoning.use": "simple"},
            overrides={},
            selection={},
            state={},
            user_id=1,
        )
    assert "模型资源" in str(excinfo.value)
