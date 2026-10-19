"""Conversation CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from ktem.services.conversations import ConversationService

from .deps import conversations as conversation_service
from .deps import current_user

router = APIRouter(prefix="/conversations", tags=["conversations"])


class UpdateBody(BaseModel):
    name: str | None = None
    is_public: bool | None = None


class FeedbackBody(BaseModel):
    message_index: int
    liked: bool
    value: str = ""


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc).strip("'"))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("")
def list_conversations(
    service: ConversationService = Depends(conversation_service),
    user: dict = Depends(current_user),
) -> dict:
    return {"items": service.list(user)}


@router.post("", status_code=201)
def create_conversation(
    service: ConversationService = Depends(conversation_service),
    user: dict = Depends(current_user),
) -> dict:
    return service.create(user)


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: str,
    service: ConversationService = Depends(conversation_service),
    user: dict = Depends(current_user),
) -> dict:
    try:
        return service.get(conversation_id, user)
    except Exception as exc:  # noqa: BLE001 - mapped to an HTTP status
        raise _translate(exc) from exc


@router.patch("/{conversation_id}")
def update_conversation(
    conversation_id: str,
    body: UpdateBody,
    service: ConversationService = Depends(conversation_service),
    user: dict = Depends(current_user),
) -> dict:
    try:
        return service.update(
            conversation_id, user, name=body.name, is_public=body.is_public
        )
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc) from exc


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    service: ConversationService = Depends(conversation_service),
    user: dict = Depends(current_user),
) -> Response:
    try:
        service.delete(conversation_id, user)
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc) from exc
    return Response(status_code=204)


@router.post("/{conversation_id}/feedback", status_code=204)
def feedback(
    conversation_id: str,
    body: FeedbackBody,
    service: ConversationService = Depends(conversation_service),
    user: dict = Depends(current_user),
) -> Response:
    try:
        service.feedback(
            conversation_id,
            user,
            message_index=body.message_index,
            liked=body.liked,
            value=body.value,
        )
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc) from exc
    return Response(status_code=204)


__all__ = ["router"]
