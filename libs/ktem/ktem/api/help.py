"""Bundled help documents, so the web UI can show them without Gradio."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from theflow.settings import settings as flowsettings

from .deps import current_user, get_app

router = APIRouter(prefix="/help", tags=["help"])

#: ``flowsettings`` lives at the repository root and points at ``<root>/docs``.
_ROOT = Path(__file__).resolve().parents[4]


def _doc_dir() -> Path:
    configured = getattr(flowsettings, "KH_DOC_DIR", None)
    if configured:
        path = Path(str(configured))
        if path.exists():
            return path
    return _ROOT / "docs"


def _read_doc(name: str, language: str) -> str:
    """Read ``<name>.<language>.md``, falling back to the English file."""
    candidates = []
    if language and language != "en":
        candidates.append(f"{name}.{language}.md")
    candidates.append(f"{name}.md")
    for candidate in candidates:
        path = _doc_dir() / candidate
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                continue
    return ""


@router.get("")
def read_help(request: Request, _: dict = Depends(current_user)) -> dict:
    app = get_app(request)
    language = str(getattr(flowsettings, "KH_UI_LANGUAGE", "en") or "en")
    return {
        "app": {
            "name": app.app_name,
            "version": app.app_version,
            "language": language,
        },
        "about_md": _read_doc("about", language),
        "usage_md": _read_doc("usage", language),
    }


__all__ = ["router"]
