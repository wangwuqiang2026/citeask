"""Configured resources: indices and the model pools the app runs with.

The classic *Resources* page edits these (and needs the Gradio forms plus a
restart for index changes). The web UI lists them read-only so people can see
what the app is actually using, and links to the classic page for editing.
Secrets live in the stored specs, so only the vendor class name and the model
name are exposed here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from ktem.db.models import engine
from ktem.services.reindex import reindex_job
from ktem.services.settings import SettingsService
from ktem.utils.i18n import tr
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .deps import admin_required, current_user, get_app
from .deps import settings_service as settings_service_dep

router = APIRouter(prefix="/resources", tags=["resources"])


class CurrentLlmBody(BaseModel):
    #: Pool name; an empty name clears the override (follow the pool default).
    name: str = Field(default="", max_length=200)


class ModelSwitchBody(BaseModel):
    #: Name of the model to run on; must exist in that pool.
    name: str = Field(min_length=1, max_length=200)


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


def _model_in_use(app, config_key: str, manager) -> set[str]:
    """The models of one pool the configured indices actually run on (§5.35/§5.36).

    An index stores the pool alias ``"default"`` rather than a model name, so the
    alias has to be resolved to the pool default before the page can badge a row.
    Several indices may use different models; every name is reported.
    """
    pool = list(manager.info().keys())
    default_name = str(getattr(manager, "_default", "") or "")
    fallback = default_name or (pool[0] if pool else "")

    names: set[str] = set()
    for index in app.index_manager.indices:
        name = str((index.config or {}).get(config_key) or "")
        if name in ("", "default"):
            name = fallback
        if name:
            names.add(name)
    return names


def _dry_index(app) -> bool:
    """True when an index has files but no chunks: an interrupted rebuild (§5.36).

    A rebuild clears the chunk relations before re-indexing. If the process dies
    halfway, the config already points at the new embedding while the stores are
    empty; the switch must be able to run again instead of reporting a no-op.
    """
    from sqlalchemy import func

    for index in app.index_manager.indices:
        try:
            Source = index._resources["Source"]
            Chunk = index._resources["Index"]
            with Session(engine) as session:
                sources = session.execute(select(func.count(Source.id))).scalar_one()
                chunks = session.execute(select(func.count(Chunk.id))).scalar_one()
        except Exception:  # noqa: BLE001 - a broken table is not a reason to block
            continue
        if sources and not chunks:
            return True
    return False


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

    embedding_rows = _vendor_rows(embeddings_info)
    embedding_in_use = _model_in_use(app, "embedding", embedding_models_manager)
    for row in embedding_rows:
        row["in_use"] = row["name"] in embedding_in_use

    reranking_rows = _vendor_rows(rerankings_info)
    reranking_in_use = _model_in_use(app, "reranking", reranking_models_manager)
    for row in reranking_rows:
        row["in_use"] = row["name"] in reranking_in_use

    return {
        "indices": _index_rows(app),
        "llms": _vendor_rows(llms_info),
        "embeddings": embedding_rows,
        "rerankings": reranking_rows,
        "mcp": [{"name": name} for name in sorted(mcp_items)],
    }


@router.put("/llm")
def set_current_llm(
    body: CurrentLlmBody,
    user: dict = Depends(current_user),
    service: SettingsService = Depends(settings_service_dep),
) -> dict:
    """Store the LLM this account's chat runs on (MODIFICATIONS §5.33).

    Persisting the choice in the account is what lets the resources page mark the
    model actually in use and keeps it across reloads and devices. An empty name
    clears the override, i.e. follow the pool default again.
    """
    from ktem.llms.manager import llms

    pool = llms.options()
    if body.name and body.name not in pool:
        raise HTTPException(status_code=400, detail="未知的模型")
    keys = service.llm_setting_keys(service.load(user["id"]))
    if not keys:
        raise HTTPException(status_code=400, detail="当前推理方式没有可设置的模型")
    service.save(user["id"], {key: body.name for key in keys})
    if body.name:
        return {"name": body.name}
    try:
        return {"name": llms.get_default_name()} if pool else {"name": ""}
    except ValueError:
        return {"name": ""}


@router.put("/embedding")
def set_current_embedding(
    body: ModelSwitchBody,
    request: Request,
    _: dict = Depends(admin_required),
) -> dict:
    """Switch the embedding model and rebuild the index in the background (§5.36).

    The old vectors are unusable with a new model (dimension and semantics), so
    the switch always ends in a full rebuild. It runs in a thread and the page
    polls ``GET /resources/embedding/job`` for progress.
    """
    from ktem.embeddings.manager import embedding_models_manager

    app = get_app(request)
    if body.name not in embedding_models_manager.options():
        raise HTTPException(status_code=400, detail="未知的模型")

    # A model can be "in use" and still need a retry: the last rebuild may have
    # failed for some files (§5.36), so only a clean job counts as a no-op.
    job = reindex_job.snapshot()
    clean = job["state"] in ("idle", "done") and not job["failed"]
    if (
        clean
        and not _dry_index(app)
        and _model_in_use(app, "embedding", embedding_models_manager) == {body.name}
    ):
        return {"started": False, "job": job}

    try:
        state = reindex_job.start(app, body.name)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"started": True, "job": state}


@router.get("/embedding/job")
def read_embedding_job(_: dict = Depends(current_user)) -> dict:
    """Progress of the last embedding switch (``state``: idle/running/done/error)."""
    return {"job": reindex_job.snapshot()}


@router.put("/reranking")
def set_current_reranking(
    body: ModelSwitchBody,
    request: Request,
    _: dict = Depends(admin_required),
) -> dict:
    """Switch the reranker; no rebuild is needed because reranking runs per query.

    Indices fall back to the pool default unless a config pins a reranker, so both
    the default flag and any explicit override are moved to the chosen model.
    """
    from ktem.rerankings.manager import reranking_models_manager

    app = get_app(request)
    info = reranking_models_manager.info()
    if body.name not in info:
        raise HTTPException(status_code=400, detail="未知的模型")

    reranking_models_manager.update(
        body.name, spec=info[body.name]["spec"], default=True
    )
    for index in app.index_manager.indices:
        config = dict(index.config or {})
        if config.get("reranking"):
            config["reranking"] = body.name
            app.index_manager.update_index(index.id, index.name, config)
    return {"name": body.name}


__all__ = ["router"]
