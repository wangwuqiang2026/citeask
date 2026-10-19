"""Chat endpoint: one question in, a Server-Sent Events stream out.

The pipeline is synchronous (LLM calls block), so it runs in a worker thread and
the events are handed to the async generator through an ``asyncio.Queue``. A
keep-alive comment is emitted while the model is thinking, so proxies and
browsers do not drop an idle connection.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ktem.services.chat import ChatService
from ktem.services.conversations import ConversationService

from .deps import chat_service as chat_service_dep
from .deps import conversations as conversations_dep
from .deps import current_user

router = APIRouter(prefix="/conversations", tags=["chat"])

KEEP_ALIVE_SECONDS = 15.0


class MessageBody(BaseModel):
    message: str = ""
    selection: dict = Field(default_factory=dict)
    overrides: dict = Field(default_factory=dict)
    regenerate: bool = False
    command: str | None = None


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: str,
    body: MessageBody,
    request: Request,
    service: ChatService = Depends(chat_service_dep),
    conv_service: ConversationService = Depends(conversations_dep),
    user: dict = Depends(current_user),
) -> StreamingResponse:
    # Fail before the stream starts, so the client gets a real status code.
    if not body.regenerate and not body.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    try:
        conv_service.get(conversation_id, user)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="会话不存在") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="无权访问该会话") from exc

    async def events() -> AsyncIterator[str]:
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def worker() -> None:
            try:
                for event in service.stream(
                    conversation_id=conversation_id,
                    user=user,
                    message=body.message,
                    selection=body.selection,
                    overrides=body.overrides,
                    regenerate=body.regenerate,
                    command=body.command,
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, event)
            except Exception as exc:  # noqa: BLE001 - reported to the client
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"event": "error", "data": {"message": str(exc)}},
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=worker, name="ktem-chat", daemon=True).start()

        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=KEEP_ALIVE_SECONDS)
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    break
                yield ": keep-alive\n\n"
                continue

            if item is None:
                break
            if await request.is_disconnected():
                break
            yield _sse(item["event"], item["data"])

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
