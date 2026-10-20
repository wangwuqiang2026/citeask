"""Conversation CRUD of the web API."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

OTHER_PASSWORD = "Abcd1234!"


def _create_other_user(logged_in) -> dict:
    """A plain account used to check what a non-owner may read or write."""
    created = logged_in.post(
        "/api/v1/users",
        json={
            "username": f"conv_other_{uuid.uuid4().hex[:8]}",
            "password": OTHER_PASSWORD,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _sign_in(logged_in, user: dict) -> TestClient:
    other = TestClient(logged_in.app)
    response = other.post(
        "/api/v1/auth/login",
        json={"username": user["username"], "password": OTHER_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return other


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


def test_public_conversation_hides_file_paths_from_non_owners(logged_in, application):
    """A public conversation is readable by others, but not the local file path.

    ``file_path`` names a file on the server; a visitor must not learn it while
    the owner still needs it to preview/open their own evidence.
    """
    from ktem.services.conversations import ConversationService

    user = logged_in.get("/api/v1/auth/me").json()["user"]
    conversation_id = logged_in.post("/api/v1/conversations", json={}).json()["id"]
    other_user = _create_other_user(logged_in)
    try:
        ConversationService(application).persist_turn(
            conv_id=conversation_id,
            user=user,
            user_message="报销标准是什么",
            assistant_message="按制度执行",
            evidence=[
                {
                    "file_name": "制度.pdf",
                    "file_path": "/srv/uploads/制度.pdf",
                    "content": "报销标准……",
                    "score": 0.9,
                }
            ],
            mindmap=None,
            plot=None,
            state={"app": {"regen": False}},
            reasoning_id="simple",
            pipeline_state={},
            selection={},
        )
        updated = logged_in.patch(
            f"/api/v1/conversations/{conversation_id}", json={"is_public": True}
        )
        assert updated.status_code == 200, updated.text

        owner_evidence = logged_in.get(
            f"/api/v1/conversations/{conversation_id}"
        ).json()["evidence_history"][0][0]
        assert owner_evidence["file_path"] == "/srv/uploads/制度.pdf"

        other = _sign_in(logged_in, other_user)
        payload = other.get(f"/api/v1/conversations/{conversation_id}")
        assert payload.status_code == 200, payload.text
        visitor_evidence = payload.json()["evidence_history"][0][0]
        assert "file_path" not in visitor_evidence
        assert visitor_evidence["file_name"] == "制度.pdf"
        assert visitor_evidence["score"] == 0.9
    finally:
        logged_in.delete(f"/api/v1/users/{other_user['id']}")
        logged_in.delete(f"/api/v1/conversations/{conversation_id}")


def test_feedback_is_owner_only(logged_in):
    """Liking a public conversation is still a write by its owner, not a reader."""
    conversation_id = logged_in.post("/api/v1/conversations", json={}).json()["id"]
    other_user = _create_other_user(logged_in)
    body = {"message_index": 0, "liked": True, "value": "good"}
    try:
        updated = logged_in.patch(
            f"/api/v1/conversations/{conversation_id}", json={"is_public": True}
        )
        assert updated.status_code == 200, updated.text

        other = _sign_in(logged_in, other_user)
        response = other.post(
            f"/api/v1/conversations/{conversation_id}/feedback", json=body
        )
        assert response.status_code == 403, response.text

        assert (
            logged_in.post(
                f"/api/v1/conversations/{conversation_id}/feedback", json=body
            ).status_code
            == 204
        )
    finally:
        logged_in.delete(f"/api/v1/users/{other_user['id']}")
        logged_in.delete(f"/api/v1/conversations/{conversation_id}")
