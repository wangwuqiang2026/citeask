"""Configured resources: indices and the model pools the app runs with.

The classic *Resources* page edits these (and needs the Gradio forms plus a
restart for index changes). The web UI lists them read-only so people can see
what the app is actually using, and links to the classic page for editing.
Secrets live in the stored specs, so only the vendor class name and the model
name are exposed here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from ktem.db.models import engine
from ktem.utils.i18n import tr
from sqlmodel import Session, select

from .deps import current_user, get_app

router = APIRouter(prefix="/resources", tags=["resources"])


def _index_rows(app) -> list[dict]:
    rows = []
    for index in app.index_manager.indices:
        count = 0
        try:
            Source = index._resources["Source"]
            with Session(engine) as session:
                count = len(session.execute(select(Source.id)).all())
        except Exception:  # noqa: BLE001 - the count is informational
            count = 0
        rows.append(
            {
                "id": index.id,
                "name": tr(index.name),
                "private": bool(index.config.get("private", False)),
                "file_count": count,
            }
        )
    return rows


def _vendor_rows(info: dict) -> list[dict]:
    """Flatten a manager's ``{name: {spec, default}}`` view without the spec."""
    rows = []
    for name, item in (info or {}).items():
        spec = item.get("spec") or {}
        vendor = str(spec.get("__type__") or "")
        model = (
            spec.get("model")
            or spec.get("model_name")
            or spec.get("model_id")
            or spec.get("model_path")
            or ""
        )
        rows.append(
            {
                "name": name,
                "vendor": vendor.rsplit(".", 1)[-1] if vendor else "",
                "model": str(model),
                "default": bool(item.get("default")),
            }
        )
    rows.sort(key=lambda row: row["name"].lower())
    return rows


@router.get("")
def read_resources(request: Request, _: dict = Depends(current_user)) -> dict:
    app = get_app(request)

    from ktem.embeddings.manager import embedding_models_manager
    from ktem.llms.manager import llms
    from ktem.mcp.manager import mcp_manager
    from ktem.rerankings.manager import reranking_models_manager

    try:
        llms_info = llms.info()
    except Exception:  # noqa: BLE001 - a partially configured app still renders
        llms_info = {}
    try:
        embeddings_info = embedding_models_manager.info()
    except Exception:  # noqa: BLE001
        embeddings_info = {}
    try:
        rerankings_info = reranking_models_manager.info()
    except Exception:  # noqa: BLE001
        rerankings_info = {}
    try:
        mcp_items = list((mcp_manager.info() or {}).keys())
    except Exception:  # noqa: BLE001
        mcp_items = []

    return {
        "indices": _index_rows(app),
        "llms": _vendor_rows(llms_info),
        "embeddings": _vendor_rows(embeddings_info),
        "rerankings": _vendor_rows(rerankings_info),
        "mcp": [{"name": name} for name in sorted(mcp_items)],
    }


__all__ = ["router"]
