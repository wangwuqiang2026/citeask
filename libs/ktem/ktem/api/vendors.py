"""Vendor (LLM / embedding / reranking) and MCP server management.

Reading the vendor catalog needs a session; changing anything is admin-only,
because a stored spec contains API keys and changing the default model affects
everybody.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ktem.services import vendors as service

from .deps import admin_required, current_user

router = APIRouter(prefix="/vendors", tags=["vendors"])


class CreateBody(BaseModel):
    name: str
    vendor: str | None = None
    params: dict | None = None
    config: dict | None = None
    default: bool = False


class UpdateBody(BaseModel):
    new_name: str | None = None
    params: dict | None = None
    config: dict | None = None
    default: bool | None = None


class TestBody(BaseModel):
    vendor: str
    params: dict = Field(default_factory=dict)


def _check_kind(kind: str) -> str:
    if kind not in service.KINDS:
        raise HTTPException(status_code=404, detail=f"未知资源类型：{kind}")
    return kind


def _translate(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        message = error.args[0] if error.args else "资源不存在"
        return HTTPException(status_code=404, detail=str(message))
    return HTTPException(status_code=400, detail=str(error))


@router.get("")
def read_catalog(_: dict = Depends(current_user)) -> dict:
    return {
        "llms": service.catalog("llms"),
        "embeddings": service.catalog("embeddings"),
        "rerankings": service.catalog("rerankings"),
        # MCP servers have no vendor list: they are plain JSON configs.
        "mcp": [],
    }


@router.get("/{kind}")
def list_entries(kind: str, user: dict = Depends(current_user)) -> dict:
    items = service.list_entries(_check_kind(kind))
    if kind == "mcp" and not user.get("admin"):
        # An MCP server config is plain JSON that can carry credentials (env
        # tokens, API keys). Only the name is needed to render the list for
        # everybody else; the admin-only detail endpoint still exposes the rest.
        items = [{"name": item["name"]} for item in items]
    return {"items": items}


@router.get("/{kind}/{name}")
def read_entry(
    kind: str, name: str, _: dict = Depends(admin_required)
) -> dict:
    try:
        return service.get_entry(_check_kind(kind), name)
    except KeyError as exc:
        raise _translate(exc) from exc


@router.post("/llms/test")
def test_llm(body: TestBody, _: dict = Depends(admin_required)) -> dict:
    return service.test_llm(body.vendor, body.params)


@router.post("/{kind}", status_code=201)
def create_entry(
    kind: str, body: CreateBody, _: dict = Depends(admin_required)
) -> dict:
    try:
        return service.create(
            _check_kind(kind),
            name=body.name,
            vendor=body.vendor,
            params=body.params,
            default=body.default,
            config=body.config,
        )
    except (ValueError, KeyError) as exc:
        raise _translate(exc) from exc


@router.patch("/{kind}/{name}")
def update_entry(
    kind: str,
    name: str,
    body: UpdateBody,
    _: dict = Depends(admin_required),
) -> dict:
    try:
        return service.update(
            _check_kind(kind),
            name,
            new_name=body.new_name,
            params=body.params,
            default=body.default,
            config=body.config,
        )
    except (ValueError, KeyError) as exc:
        raise _translate(exc) from exc


def _is_default_model(kind: str, name: str) -> bool:
    """Whether ``name`` is the model row flagged as the pool default.

    Only the stored flag counts here. ``get_default_name()`` must not be used as
    the guard: when no row carries the flag it falls back to a *random* model, so
    a pool with a single model would refuse to delete it ("该模型是当前默认模型"
    with nothing to switch to) and a larger pool would accept or refuse the same
    deletion depending on a coin flip.
    """
    if kind == "mcp":
        return False
    info = service._manager(kind).info()  # noqa: SLF001 - same package, one manager
    return bool((info.get(name) or {}).get("default"))


@router.delete("/{kind}/{name}", status_code=204)
def delete_entry(
    kind: str, name: str, _: dict = Depends(admin_required)
) -> Response:
    kind = _check_kind(kind)
    if _is_default_model(kind, name):
        raise HTTPException(status_code=409, detail="该模型是当前默认模型，请先切换")
    try:
        service.delete(kind, name)
    except (ValueError, KeyError) as exc:
        raise _translate(exc) from exc
    return Response(status_code=204)


__all__ = ["router"]
