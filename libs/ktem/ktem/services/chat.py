"""Chat orchestration for the web API.

This is the Gradio-free counterpart of ``ChatPage.chat_fn``: it builds the same
reasoning pipeline from the same settings and retrievers, turns the pipeline's
``Document`` stream into transport-neutral events, and persists the turn through
:class:`ConversationService` in the storage format the classic UI also reads.

The events yielded here are plain dicts ``{"event": name, "data": {...}}``; the
HTTP layer serialises them as Server-Sent Events.
"""

from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from typing import Any, Iterator

from ktem.components import reasonings
from ktem.db.models import engine
from ktem.reasoning.prompt_optimization.suggest_conversation_name import (
    SuggestConvNamePipeline,
)
from ktem.reasoning.prompt_optimization.suggest_followup_chat import (
    SuggestFollowupQuesPipeline,
)
from ktem.services.conversations import ConversationService
from ktem.services.settings import SettingsService
from ktem.utils import SUPPORTED_LANGUAGE_MAP, prepare_llm_query
from ktem.utils.commands import WEB_SEARCH_COMMAND
from ktem.utils.i18n import tr
from ktem.utils.selector import (
    SELECTOR_MODE_ALL,
    SELECTOR_MODE_DISABLED,
    SELECTOR_MODE_SELECT,
)
from kotaemon.base import Document
from kotaemon.indices.qa.utils import strip_think_tag
from sqlmodel import Session, select
from theflow.settings import settings as flowsettings
from theflow.utils.modules import import_dotted_string

#: Same wording as the classic page (pages/chat/__init__.py).
DEFAULT_QUESTION = "What is the summary of this document?"
DEFAULT_STATE = {"app": {"regen": False}}
EMPTY_ANSWER = "(Sorry, I don't know)"
THINKING_PLACEHOLDER = "Thinking ..."
NO_FILES_WARNING = (
    "当前没有可检索的文件：请先上传并等待索引完成；"
    "如果检索范围选的是「在文件中搜索」，还需要选中文件。"
)

KH_WEB_SEARCH_BACKEND = getattr(flowsettings, "KH_WEB_SEARCH_BACKEND", None)
WebSearch = None
if KH_WEB_SEARCH_BACKEND:
    try:
        WebSearch = import_dotted_string(KH_WEB_SEARCH_BACKEND, safe=False)
    except (ImportError, AttributeError) as exc:  # noqa: BLE001 - optional feature
        print(f"web api: web search backend unavailable: {exc}")


def _selection_tuple(selection: dict | None, index_id: int) -> tuple[str, list, str | None]:
    config = (selection or {}).get(str(index_id)) or {}
    mode = config.get("mode") or SELECTOR_MODE_ALL
    if mode not in (SELECTOR_MODE_ALL, SELECTOR_MODE_SELECT, SELECTOR_MODE_DISABLED):
        mode = SELECTOR_MODE_ALL
    file_ids = [item for item in (config.get("file_ids") or []) if item not in (None, "")]
    return mode, file_ids, None


_MISSING = object()


def _uses_selector(index) -> bool:
    """Whether the index takes part in retrieval scoping.

    ``selector`` is assigned by the Gradio page while the UI is built. The API
    must also work when only ``App()`` was constructed (tests, headless use), so
    a *missing* attribute means "no UI decided yet" and the index is included;
    an explicit ``None`` means the index has no selector and is skipped.
    """
    selector = getattr(index, "selector", _MISSING)
    return selector is _MISSING or selector is not None


class ChatService:
    """Stream one chat turn as events and persist the result."""

    def __init__(self, app):
        self._app = app
        self._conversations = ConversationService(app)
        self._settings = SettingsService(app)

    # --------------------------------------------------------------- scope
    def _all_file_ids(self, index, user_id: Any) -> list:
        Source = index._resources["Source"]
        with Session(engine) as session:
            statement = select(Source.id)
            if index.config.get("private", False):
                statement = statement.where(Source.user == user_id)
            return [row[0] for row in session.execute(statement).all()]

    def _scoped_ids(self, index, selection: dict | None, user_id: Any) -> list:
        """Resolve the retrieval scope the request asks for, for one index."""
        mode, file_ids, _ = _selection_tuple(selection, index.id)
        if mode == SELECTOR_MODE_DISABLED:
            return []
        available = self._all_file_ids(index, user_id)
        if mode == SELECTOR_MODE_SELECT:
            chosen = [file_id for file_id in file_ids if file_id in available]
            # empty selection under "search in file(s)" means "all files", the
            # same fallback the classic selector applies (MODIFICATIONS §5.16)
            return chosen or available
        return available

    # -------------------------------------------------------------- pipeline
    def build_pipeline(
        self,
        settings: dict,
        overrides: dict,
        selection: dict,
        state: dict,
        user_id: Any,
        command: str | None = None,
    ):
        """Build the reasoning pipeline, mirroring ``ChatPage.create_pipeline``."""
        reasoning_mode = (overrides or {}).get("reasoning") or settings.get(
            "reasoning.use"
        )
        reasoning_cls = reasonings.get(reasoning_mode)
        if reasoning_cls is None:
            raise ValueError(f"未知的推理方式：{reasoning_mode}")
        reasoning_id = reasoning_cls.get_info()["id"]

        tuned = deepcopy(settings)
        llm = (overrides or {}).get("llm")
        if llm:
            tuned[f"reasoning.options.{reasoning_id}.llm"] = llm
        mindmap = (overrides or {}).get("mindmap")
        if mindmap is not None:
            tuned["reasoning.options.simple.create_mindmap"] = mindmap
        citation = (overrides or {}).get("citation")
        if citation:
            tuned["reasoning.options.simple.highlight_citation"] = citation
        language = (overrides or {}).get("language")
        if language:
            tuned["reasoning.lang"] = language

        retrievers = []
        if command == WEB_SEARCH_COMMAND:
            if WebSearch is None:
                raise ValueError("Web 搜索后端不可用")
            retrievers.append(WebSearch())
        else:
            for index in self._app.index_manager.indices:
                if not _uses_selector(index):
                    continue
                mode, file_ids, _ = _selection_tuple(selection, index.id)
                retrievers += index.get_retriever_pipelines(
                    tuned, user_id, (mode, file_ids, user_id)
                )

        reasoning_state = {
            "app": deepcopy((state or {}).get("app", {"regen": False})),
            "pipeline": deepcopy((state or {}).get(reasoning_id, {})),
        }
        pipeline = reasoning_cls.get_pipeline(tuned, reasoning_state, retrievers)
        return pipeline, reasoning_state, reasoning_id

    # ----------------------------------------------------------------- title
    @staticmethod
    def _suggest_name(pairs: list) -> str | None:
        try:
            text = SuggestConvNamePipeline()(pairs).text
            text = strip_think_tag(text).replace('"', "").replace("'", "")[:40]
            return text.strip() or None
        except Exception as exc:  # noqa: BLE001 - naming is a nicety
            print(f"web api: could not suggest a conversation name: {exc}")
            return None

    def _suggestions(self, settings: dict, overrides: dict, pairs: list) -> list[str]:
        if not getattr(flowsettings, "KH_FEATURE_CHAT_SUGGESTION", False):
            return []
        try:
            language = (overrides or {}).get("language") or settings.get(
                "reasoning.lang", "en"
            )
            pipeline = SuggestFollowupQuesPipeline()
            pipeline.lang = SUPPORTED_LANGUAGE_MAP.get(language, "English")
            response = pipeline(pairs).text
            match = re.search(r"\[(.*?)\]", re.sub("\n", "", response))
            if not match:
                return []
            questions = json.loads(match.group())
            return [str(item) for item in questions][:5]
        except Exception as exc:  # noqa: BLE001 - suggestions are optional
            print(f"web api: could not suggest follow-up questions: {exc}")
            return []

    # ----------------------------------------------------------------- stream
    def stream(
        self,
        *,
        conversation_id: str,
        user: dict,
        message: str,
        selection: dict | None = None,
        overrides: dict | None = None,
        regenerate: bool = False,
        command: str | None = None,
    ) -> Iterator[dict]:
        """Yield ``{"event", "data"}`` dicts for one question."""
        message = (message or "").strip()
        selection = selection or {}
        overrides = overrides or {}

        pairs, state = self._conversations.history_for_pipeline(conversation_id, user)
        if regenerate:
            if not pairs:
                raise ValueError("没有可以重新生成的回答")
            message = pairs[-1][0]
            pairs = pairs[:-1]
            state = {
                **state,
                "app": {**state.get("app", DEFAULT_STATE["app"]), "regen": True},
            }

        settings = self._settings.load(user.get("id"))
        scoped = [
            self._scoped_ids(index, selection, user.get("id"))
            for index in self._app.index_manager.indices
            if _uses_selector(index)
        ]
        has_files = any(scoped)
        llm_query = prepare_llm_query(
            message,
            has_selected_files=has_files,
            default_question=DEFAULT_QUESTION,
        )

        message_id = uuid.uuid4().hex
        start_data: dict[str, Any] = {
            "message_id": message_id,
            "placeholder": THINKING_PLACEHOLDER,
            "regenerate": regenerate,
        }
        if not has_files:
            start_data["warning"] = NO_FILES_WARNING
        yield {"event": "start", "data": start_data}

        try:
            pipeline, reasoning_state, reasoning_id = self.build_pipeline(
                settings, overrides, selection, state, user.get("id"), command
            )
        except Exception as exc:  # noqa: BLE001 - surface the reason to the UI
            yield {"event": "error", "data": {"message": str(exc)}}
            return

        text = ""
        evidence: list[dict] = []
        mindmap: str | None = None
        plot: Any = None
        try:
            for response in pipeline.stream(llm_query, conversation_id, pairs):
                if not isinstance(response, Document):
                    continue
                channel = response.channel
                if channel == "chat":
                    if response.content is None:
                        text = ""
                        yield {"event": "reset", "data": {}}
                    else:
                        delta = str(response.content)
                        text += delta
                        yield {"event": "token", "data": {"delta": delta}}
                elif channel == "evidence":
                    if isinstance(response.content, list):
                        evidence = response.content
                        yield {"event": "evidence", "data": {"items": evidence}}
                elif channel == "mindmap":
                    if response.content:
                        mindmap = str(response.content)
                        yield {
                            "event": "mindmap",
                            "data": {"markdown": mindmap},
                        }
                elif channel == "plot":
                    plot = response.content
                    yield {"event": "plot", "data": {"json": plot}}
                # ``info`` (the legacy HTML panel) is intentionally ignored: the
                # web UI renders the structured ``evidence`` channel instead.
        except Exception as exc:  # noqa: BLE001 - keep the stream well-formed
            yield {"event": "error", "data": {"message": str(exc)}}
            return

        if not text:
            text = str(getattr(flowsettings, "KH_CHAT_EMPTY_MSG_PLACEHOLDER", EMPTY_ANSWER))
            yield {"event": "token", "data": {"delta": text}}

        new_name = None
        if not regenerate and not pairs and text:
            new_name = self._suggest_name(pairs + [[message, text]])

        try:
            self._conversations.persist_turn(
                conv_id=conversation_id,
                user=user,
                user_message=message,
                assistant_message=text,
                evidence=evidence,
                mindmap=mindmap,
                plot=plot,
                state=state,
                reasoning_id=reasoning_id,
                pipeline_state=reasoning_state.get("pipeline", {}),
                selection=selection,
                regenerate=regenerate,
                name=new_name,
            )
        except Exception as exc:  # noqa: BLE001 - a failed save must be visible
            yield {"event": "error", "data": {"message": f"保存会话失败：{exc}"}}
            return

        yield {"event": "done", "data": {"message_id": message_id, "name": new_name}}

        if new_name:
            yield {"event": "title", "data": {"name": new_name}}

        suggestions = self._suggestions(
            settings, overrides, pairs + [[message, text]]
        )
        if suggestions:
            yield {"event": "suggestions", "data": {"items": suggestions}}


__all__ = ["ChatService", "DEFAULT_QUESTION", "DEFAULT_STATE"]
