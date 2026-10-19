"""Conversation CRUD of the web API."""

from __future__ import annotations


def test_create_get_rename_delete(logged_in):
    created = logged_in.post("/api/v1/conversations", json={})
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    detail = logged_in.get(f"/api/v1/conversations/{conversation_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["messages"] == []
    assert payload["owned"] is True
    assert payload["state"]["app"]["regen"] is False

    renamed = logged_in.patch(
        f"/api/v1/conversations/{conversation_id}", json={"name": "预算问答"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "预算问答"

    listed = logged_in.get("/api/v1/conversations").json()["items"]
    assert any(item["id"] == conversation_id for item in listed)

    assert logged_in.delete(f"/api/v1/conversations/{conversation_id}").status_code == 204
    assert logged_in.get(f"/api/v1/conversations/{conversation_id}").status_code == 404


def test_name_validation(logged_in):
    conversation_id = logged_in.post("/api/v1/conversations", json={}).json()["id"]
    too_long = "x" * 41
    response = logged_in.patch(
        f"/api/v1/conversations/{conversation_id}", json={"name": too_long}
    )
    assert response.status_code == 400
    assert "40" in response.json()["detail"]
    logged_in.delete(f"/api/v1/conversations/{conversation_id}")


def test_unknown_conversation_is_a_404(logged_in):
    assert logged_in.get("/api/v1/conversations/does-not-exist").status_code == 404
    assert logged_in.delete("/api/v1/conversations/does-not-exist").status_code == 404


def test_feedback_is_accepted(logged_in):
    conversation_id = logged_in.post("/api/v1/conversations", json={}).json()["id"]
    response = logged_in.post(
        f"/api/v1/conversations/{conversation_id}/feedback",
        json={"message_index": 0, "liked": True, "value": "good"},
    )
    assert response.status_code == 204
    logged_in.delete(f"/api/v1/conversations/{conversation_id}")


def test_mindmap_is_stored_next_to_its_answer(logged_in, application):
    """The chat stream emits a ``mindmap`` channel; the web UI needs it later."""
    from ktem.services.conversations import ConversationService

    user = logged_in.get("/api/v1/auth/me").json()["user"]
    conversation_id = logged_in.post("/api/v1/conversations", json={}).json()["id"]

    def persist(mindmap: str, regenerate: bool = False) -> None:
        ConversationService(application).persist_turn(
            conv_id=conversation_id,
            user=user,
            user_message="总结这份通知",
            assistant_message="通知共三条",
            evidence=[],
            mindmap=mindmap,
            plot=None,
            state={"app": {"regen": regenerate}},
            reasoning_id="simple",
            pipeline_state={},
            selection={},
            regenerate=regenerate,
        )

    try:
        persist("- 奖学金\n  - 申请条件")
        payload = logged_in.get(f"/api/v1/conversations/{conversation_id}").json()
        assert payload["mindmap_history"] == ["- 奖学金\n  - 申请条件"]

        # Regenerating replaces the map of the last answer instead of appending.
        persist("- 奖学金\n  - 截止日期", regenerate=True)
        payload = logged_in.get(f"/api/v1/conversations/{conversation_id}").json()
        assert payload["mindmap_history"] == ["- 奖学金\n  - 截止日期"]
        assert len(payload["messages"]) == 2
    finally:
        logged_in.delete(f"/api/v1/conversations/{conversation_id}")
