"""Conversation storage and access rules for the web API.

The storage format is the one the classic UI already writes into
``Conversation.data_source`` (``[[user, bot], ...]`` plus retrieval/plot history
and the reasoning state), so both UIs can read the same conversations. The web
UI adds two keys next to the legacy ones:

* ``evidence_history`` - structured evidence per answer (see ``services.chat``);
* ``selected_web`` - the retrieval scope chosen in the web UI, kept apart from
  the Gradio-specific ``selected`` values so the classic page keeps working.

Reads are allowed for the owner, and for everybody when a conversation is public;
writes are owner-only.
"""

from __future__ import annotations

import datetime
import re
from copy import deepcopy
from typing import Any

from ktem.db.models import Conversation, engine
from ktem.utils.conversation import sync_retrieval_n_message
from sqlmodel import Session, or_, select
from theflow.settings import settings as flowsettings

_TAG = re.compile(r"<[^>]+>")


def _iso(value: datetime.datetime | None) -> str | None:
    return value.isoformat() if value else None


def _preview(data_source: dict) -> str:
    """First user message of the conversation, as plain text."""
    for item in data_source.get("messages", []):
        if isinstance(item, (list, tuple)) and item:
            text = str(item[0] or "").strip()
            if text:
                return _TAG.sub("", text)[:120]
    return ""


def _flatten_messages(data_source: dict) -> list[dict]:
    """``[[user, bot], ...]`` (legacy) -> ``[{role, content}]`` (web)."""
    messages: list[dict] = []
    for item in data_source.get("messages", []):
        if isinstance(item, (list, tuple)):
            if len(item) < 2:
                user, bot = (item[0] if item else ""), ""
            else:
                user, bot = item[0], item[1]
            if user:
                messages.append({"role": "user", "content": str(user)})
            if bot:
                messages.append({"role": "assistant", "content": str(bot)})
        elif isinstance(item, dict) and item.get("role"):
            messages.append(item)
    return messages


class ConversationService:
    """Create, read, update and persist conversations."""

    def __init__(self, app):
        self._app = app

    # ------------------------------------------------------------------ read
    def _can_see_public(self, user: dict) -> bool:
        """Mirror the visibility rule of ``pages/chat/control.py``."""
        admin_username = getattr(flowsettings, "KH_USER_CAN_SEE_PUBLIC", None)
        if not admin_username:
            return True
        return user.get("username") == admin_username

    def _row(self, conv_id: str) -> Conversation:
        with Session(engine) as session:
            row = session.exec(
                select(Conversation).where(Conversation.id == conv_id)
            ).first()
        if row is None:
            raise KeyError("会话不存在")
        return row

    @staticmethod
    def _is_owner(row: Conversation, user: dict) -> bool:
        return str(row.user) == str(user.get("id"))

    def _can_read(self, row: Conversation, user: dict) -> bool:
        if self._is_owner(row, user):
            return True
        if row.is_public and self._can_see_public(user):
            return True
        return bool(user.get("admin")) and row.is_public

    def list(self, user: dict) -> list[dict]:
        with Session(engine) as session:
            if self._can_see_public(user):
                statement = select(Conversation).where(
                    or_(
                        Conversation.user == user.get("id"),
                        Conversation.is_public,
                    )
                )
            else:
                statement = select(Conversation).where(
                    Conversation.user == user.get("id")
                )
            rows = session.exec(statement).all()

        items = [
            {
                "id": row.id,
                "name": row.name,
                "is_public": bool(row.is_public),
                "date_created": _iso(row.date_created),
                "date_updated": _iso(row.date_updated),
                "preview": _preview(row.data_source or {}),
                "owned": self._is_owner(row, user),
            }
            for row in rows
        ]
        items.sort(
            key=lambda item: (item["date_updated"] or item["date_created"] or ""),
            reverse=True,
        )
        return items

    def get(self, conv_id: str, user: dict) -> dict:
        row = self._row(conv_id)
        if not self._can_read(row, user):
            raise PermissionError("无权访问该会话")
        owner = self._is_owner(row, user)
        data = deepcopy(row.data_source or {})

        messages = _flatten_messages(data)
        evidence_history = data.get("evidence_history")
        if not isinstance(evidence_history, list):
            evidence_history = []
        # keep one evidence slot per stored Q/A pair
        pair_count = len(messages) // 2 + len(messages) % 2
        evidence_history = list(evidence_history[:pair_count])
        while len(evidence_history) < pair_count:
            evidence_history.append([])
        if not owner:
            # A public conversation is readable by others, but the local storage
            # path is not part of what they may see. Only the owner needs it.
            for slot in evidence_history:
                if not isinstance(slot, list):
                    continue
                for item in slot:
                    if isinstance(item, dict):
                        item.pop("file_path", None)

        mindmap_history = data.get("mindmap_history")
        if not isinstance(mindmap_history, list):
            mindmap_history = []
        mindmap_history = list(mindmap_history[:pair_count])
        while len(mindmap_history) < pair_count:
            mindmap_history.append(None)

        return {
            "id": row.id,
            "name": row.name,
            "is_public": bool(row.is_public),
            "owned": self._is_owner(row, user),
            "date_created": _iso(row.date_created),
            "date_updated": _iso(row.date_updated),
            "messages": messages,
            "evidence_history": evidence_history,
            "mindmap_history": mindmap_history,
            "legacy_evidence": data.get("retrieval_messages", []),
            "plot_history": data.get("plot_history", []),
            "selected": data.get("selected_web", {}),
            "state": data.get("state", {"app": {"regen": False}}),
        }

    # ----------------------------------------------------------------- write
    def create(self, user: dict) -> dict:
        with Session(engine) as session:
            row = Conversation(user=user.get("id"))
            session.add(row)
            session.commit()
            session.refresh(row)
        return {"id": row.id, "name": row.name, "is_public": False}

    @staticmethod
    def validate_name(name: str) -> str:
        name = (name or "").strip()
        if not name:
            raise ValueError("名称不能为空")
        if len(name) > 40:
            raise ValueError("名称不能超过 40 个字符")
        return name

    def update(
        self,
        conv_id: str,
        user: dict,
        *,
        name: str | None = None,
        is_public: bool | None = None,
    ) -> dict:
        row = self._row(conv_id)
        if not self._is_owner(row, user):
            raise PermissionError("只有会话所有者可以修改")
        with Session(engine) as session:
            stored = session.exec(
                select(Conversation).where(Conversation.id == conv_id)
            ).one()
            if name is not None:
                stored.name = self.validate_name(name)
            if is_public is not None:
                stored.is_public = bool(is_public)
            stored.date_updated = datetime.datetime.now()
            session.add(stored)
            session.commit()
            return {
                "id": stored.id,
                "name": stored.name,
                "is_public": bool(stored.is_public),
            }

    def delete(self, conv_id: str, user: dict) -> None:
        row = self._row(conv_id)
        if not self._is_owner(row, user):
            raise PermissionError("只有会话所有者可以删除")
        with Session(engine) as session:
            stored = session.exec(
                select(Conversation).where(Conversation.id == conv_id)
            ).one()
            session.delete(stored)
            session.commit()

    def feedback(
        self, conv_id: str, user: dict, *, message_index: int, liked: bool, value: str
    ) -> None:
        row = self._row(conv_id)
        if not self._is_owner(row, user):
            raise PermissionError("只有会话所有者可以反馈")
        with Session(engine) as session:
            stored = session.exec(
                select(Conversation).where(Conversation.id == conv_id)
            ).one()
            data = deepcopy(stored.data_source or {})
            likes = data.get("likes", [])
            likes.append([message_index, value, liked])
            data["likes"] = likes
            stored.data_source = data
            session.add(stored)
            session.commit()

    # --------------------------------------------------------------- persist
    def persist_turn(
        self,
        *,
        conv_id: str,
        user: dict,
        user_message: str,
        assistant_message: str,
        evidence: list[dict],
        mindmap: str | None = None,
        plot: Any,
        state: dict,
        reasoning_id: str,
        pipeline_state: dict,
        selection: dict,
        regenerate: bool = False,
        name: str | None = None,
    ) -> None:
        """Write one question/answer pair into the conversation.

        ``regenerate`` replaces the assistant half of the last pair instead of
        appending, which is what the UI's regenerate button means.
        """
        row = self._row(conv_id)
        if not self._is_owner(row, user):
            raise PermissionError("只有会话所有者可以写入")

        with Session(engine) as session:
            stored = session.exec(
                select(Conversation).where(Conversation.id == conv_id)
            ).one()
            data = deepcopy(stored.data_source or {})
            messages = list(data.get("messages", []))
            retrieval = sync_retrieval_n_message(
                messages, list(data.get("retrieval_messages", []))
            )
            plots = list(data.get("plot_history", []))
            evidence_history = list(data.get("evidence_history", []))
            mindmaps = list(data.get("mindmap_history", []))

            while len(plots) < len(messages):
                plots.append(None)
            while len(evidence_history) < len(messages):
                evidence_history.append([])
            while len(mindmaps) < len(messages):
                mindmaps.append(None)

            if regenerate and messages:
                messages[-1] = [messages[-1][0], assistant_message]
                evidence_history[-1] = evidence
                mindmaps[-1] = mindmap
                if plots:
                    plots[-1] = plot
                else:
                    plots.append(plot)
            else:
                messages.append([user_message, assistant_message])
                evidence_history.append(evidence)
                mindmaps.append(mindmap)
                plots.append(plot)
                retrieval.append("")

            # keep every per-message list aligned with the messages list
            retrieval = sync_retrieval_n_message(messages, retrieval)
            while len(plots) < len(messages):
                plots.append(None)
            while len(evidence_history) < len(messages):
                evidence_history.append([])
            while len(mindmaps) < len(messages):
                mindmaps.append(None)

            app_state = deepcopy(state.get("app", {"regen": False}))
            app_state["regen"] = False
            state = {**state, "app": app_state, reasoning_id: pipeline_state}

            data.update(
                {
                    "messages": messages,
                    "retrieval_messages": retrieval,
                    "evidence_history": evidence_history,
                    "mindmap_history": mindmaps,
                    "plot_history": plots,
                    "state": state,
                    "selected_web": selection,
                }
            )
            stored.data_source = data
            if name:
                stored.name = self.validate_name(name)
            stored.date_updated = datetime.datetime.now()
            session.add(stored)
            session.commit()

    def history_for_pipeline(self, conv_id: str, user: dict) -> tuple[list, dict]:
        """The ``[[user, bot], ...]`` history and state the pipelines expect."""
        payload = self.get(conv_id, user)
        pairs: list[list[str]] = []
        for item in self._raw_messages(conv_id):
            if isinstance(item, (list, tuple)) and len(item) == 2:
                pairs.append([str(item[0] or ""), str(item[1] or "")])
        return pairs, payload.get("state") or {"app": {"regen": False}}

    def _raw_messages(self, conv_id: str) -> list:
        row = self._row(conv_id)
        return list((row.data_source or {}).get("messages", []))


__all__ = ["ConversationService"]
