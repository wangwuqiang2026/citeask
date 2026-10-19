"""Application metadata for the web UI: what the frontend needs before it can
render its controls (feature flags, index list, reasoning/model/language
choices). Every label is translated on the Python side, so the frontend never
needs to know the localization catalog.
"""

from __future__ import annotations

from decouple import config
from fastapi import APIRouter, Depends, Request
from ktem.components import reasonings
from ktem.db.models import engine
from ktem.utils.i18n import tr
from sqlmodel import Session, select
from theflow.settings import settings as flowsettings

from .deps import current_user, get_app

router = APIRouter(prefix="/meta", tags=["meta"])


def _choices(item) -> list[dict]:
    output = []
    for choice in getattr(item, "choices", []) or []:
        if isinstance(choice, (list, tuple)) and len(choice) == 2:
            output.append({"label": tr(str(choice[0])), "value": choice[1]})
        else:
            output.append({"label": tr(str(choice)), "value": choice})
    return output


def _index_info(app) -> list[dict]:
    indices = []
    for index in app.index_manager.indices:
        count = 0
        try:
            Source = index._resources["Source"]
            with Session(engine) as session:
                statement = select(Source.id)
                count = len(session.execute(statement).all())
        except Exception:  # noqa: BLE001 - the count is informational
            count = 0
        indices.append(
            {
                "id": index.id,
                "name": tr(index.name),
                "private": bool(index.config.get("private", False)),
                "file_count": count,
                "has_selector": getattr(index, "selector", None) is not None,
            }
        )
    return indices


@router.get("")
def meta(request: Request, user: dict = Depends(current_user)) -> dict:
    app = get_app(request)
    from ktem.services.chat import WebSearch

    settings = app.default_settings
    use_mindmap = not config("USE_LOW_LLM_REQUESTS", default=False, cast=bool)

    reasoning_choices = []
    for mode_id, reasoning_cls in reasonings.items():
        try:
            label = tr(str(reasoning_cls.get_info().get("name", mode_id)))
        except Exception:  # noqa: BLE001
            label = mode_id
        reasoning_choices.append({"value": mode_id, "label": label})

    lang_item = settings.reasoning.settings.get("lang")
    citation_item = settings.reasoning.options.get("simple")
    citation_item = (
        citation_item.settings.get("highlight_citation") if citation_item else None
    )

    from ktem.llms.manager import llms

    try:
        model_names = list(llms.options().keys())
    except Exception:  # noqa: BLE001 - no model configured yet
        model_names = []
    models = [{"value": "", "label": tr("(default)")}] + [
        {"value": name, "label": name} for name in model_names
    ]

    return {
        "app": {
            "name": app.app_name,
            "version": app.app_version,
            "language": getattr(flowsettings, "KH_UI_LANGUAGE", "en"),
        },
        "user": user,
        "features": {
            "user_management": bool(app.f_user_management),
            "chat_suggestion": bool(
                getattr(flowsettings, "KH_FEATURE_CHAT_SUGGESTION", False)
            ),
            "web_search": WebSearch is not None,
            "mindmap": use_mindmap,
            "demo_mode": bool(getattr(flowsettings, "KH_DEMO_MODE", False)),
        },
        "indices": _index_info(app),
        "reasoning": {
            "choices": reasoning_choices,
            "default": settings.reasoning.settings["use"].value
            if "use" in settings.reasoning.settings
            else (reasoning_choices[0]["value"] if reasoning_choices else ""),
        },
        "models": {"choices": models, "default": ""},
        "languages": {
            "choices": _choices(lang_item) if lang_item else [],
            "default": lang_item.value if lang_item else "zh",
        },
        "citations": {
            "choices": _choices(citation_item) if citation_item else [],
            "default": citation_item.value if citation_item else "inline",
        },
    }


__all__ = ["router"]
