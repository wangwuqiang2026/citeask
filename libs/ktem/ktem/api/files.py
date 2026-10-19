"""File and file-group endpoints of the web API.

The router is mounted without a path prefix: the contract spans two prefixes
(``/files`` and ``/groups``) and a single ``APIRouter`` has to serve both, so
every route below declares its full path. ``ktem/api/__init__.py`` includes the
router as-is; the ``/api/v1`` prefix is added by the application host.

Every route requires a signed-in user (``current_user`` from ``deps``) and
returns JSON except the two indexing routes, which stream server-sent events in
the format the classic UI's output boxes used to show:

    event: progress  data: {"line": "✅ | a.pdf"}
    event: done      data: {"ids": ["..."], "errors": []}
    event: error     data: {"message": "..."}

The blocking readers/embeddings run inside a synchronous generator, which
Starlette iterates in a worker thread — the event loop is never blocked.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from ktem.services.files import FileService, sse_frame

from .deps import current_user, get_app

router = APIRouter(tags=["files"])

#: Headers that stop proxies and browsers from buffering an event stream.
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


class GroupBody(BaseModel):
    name: str
    files: list[str] = []


class GroupPatchBody(BaseModel):
    name: Optional[str] = None
    files: Optional[list[str]] = None


def file_service(app=Depends(get_app)) -> FileService:
    """The file service bound to the running application."""
    return FileService(app)


def _translate(exc: Exception) -> HTTPException:
    """Map a service exception onto the HTTP status the API documents."""
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc).strip("'"))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------- files
@router.get("/files")
def list_files(
    index_id: Optional[int] = Query(default=None),
    query: str = Query(default=""),
    service: FileService = Depends(file_service),
    user: dict = Depends(current_user),
) -> dict:
    """The file list of one index (id/name/type/size/blocks/loader/profile/...)."""
    try:
        return service.list_files(index_id, user, query)
    except Exception as exc:  # noqa: BLE001 - mapped to an HTTP status
        raise _translate(exc) from exc


@router.post("/files/upload")
def upload_files(
    files: list[UploadFile] = File(default=[]),
    urls: str = Form(default=""),
    index_id: Optional[int] = Form(default=None),
    reindex: bool = Form(default=False),
    service: FileService = Depends(file_service),
    user: dict = Depends(current_user),
) -> StreamingResponse:
    """Upload files and/or URLs, then stream the indexing progress as SSE."""
    work_dir = service.upload_tempdir()
    try:
        paths = _save_uploads(files, work_dir)
        url_list = [line.strip() for line in (urls or "").splitlines() if line.strip()]
        index = service.resolve_index(index_id)
        if not paths and not url_list:
            raise HTTPException(status_code=400, detail="没有选择文件或网址")
    except Exception as exc:  # noqa: BLE001 - the scratch dir must not leak
        shutil.rmtree(work_dir, ignore_errors=True)
        if isinstance(exc, HTTPException):
            raise
        raise _translate(exc) from exc

    generator = service.stream_paths(
        index, user, paths, url_list, reindex=reindex, cleanup_dir=work_dir
    )
    return StreamingResponse(
        (_frame(event, data) for event, data in generator),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


def _save_uploads(files: list[UploadFile], work_dir: Path) -> list[Path]:
    """Write the multipart files into the request's scratch directory.

    Only the last path segment is kept (a browser may send a full Windows path),
    and a repeated name is given a numeric suffix instead of overwriting the
    previous file — both rules protect the temp directory from the client.
    """
    paths: list[Path] = []
    for upload in files or []:
        name = Path((upload.filename or "").replace("\\", "/")).name
        if name in ("", ".", ".."):
            continue
        target = work_dir / name
        counter = 1
        while target.exists():
            target = work_dir / f"{Path(name).stem}-{counter}{Path(name).suffix}"
            counter += 1
        with target.open("wb") as out:
            shutil.copyfileobj(upload.file, out)
        paths.append(target)
    return paths


@router.delete("/files/{file_id}")
def delete_file(
    file_id: str,
    service: FileService = Depends(file_service),
    user: dict = Depends(current_user),
) -> dict:
    """Remove a source row, its chunks (docstore + vector store) and the upload."""
    try:
        return service.delete_file(file_id, user)
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc) from exc


@router.post("/files/{file_id}/reindex")
def reindex_file(
    file_id: str,
    service: FileService = Depends(file_service),
    user: dict = Depends(current_user),
) -> StreamingResponse:
    """Re-parse a stored upload and stream the progress (same frames as upload)."""
    try:
        index, copy, work_dir = service.prepare_reindex(file_id, user)
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc) from exc

    generator = service.stream_paths(
        index, user, [copy], reindex=True, cleanup_dir=work_dir
    )
    return StreamingResponse(
        (_frame(event, data) for event, data in generator),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get("/files/{file_id}/chunks")
def file_chunks(
    file_id: str,
    chunk_type: str = Query(default="all", alias="type"),
    service: FileService = Depends(file_service),
    user: dict = Depends(current_user),
) -> dict:
    """The chunk drawer: header, per-type counts and the chunks themselves."""
    try:
        return service.chunks(file_id, user, chunk_type)
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc) from exc


@router.get("/files/{file_id}/download")
def download_file(
    file_id: str,
    service: FileService = Depends(file_service),
    user: dict = Depends(current_user),
) -> FileResponse:
    """The original upload (404 when the stored copy is gone or it is a URL)."""
    try:
        path, filename = service.download(file_id, user)
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc) from exc
    return FileResponse(path, filename=filename)


# --------------------------------------------------------------------- groups
@router.get("/groups")
def list_groups(
    index_id: Optional[int] = Query(default=None),
    service: FileService = Depends(file_service),
    user: dict = Depends(current_user),
) -> dict:
    try:
        return service.list_groups(index_id, user)
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc) from exc


@router.post("/groups")
def create_group(
    body: GroupBody,
    service: FileService = Depends(file_service),
    user: dict = Depends(current_user),
) -> dict:
    try:
        return service.create_group(None, user, body.name, body.files)
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc) from exc


@router.patch("/groups/{group_id}")
def update_group(
    group_id: str,
    body: GroupPatchBody,
    service: FileService = Depends(file_service),
    user: dict = Depends(current_user),
) -> dict:
    try:
        return service.update_group(
            group_id, user, name=body.name, files=body.files
        )
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc) from exc


@router.delete("/groups/{group_id}")
def delete_group(
    group_id: str,
    service: FileService = Depends(file_service),
    user: dict = Depends(current_user),
) -> dict:
    try:
        return service.delete_group(group_id, user)
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc) from exc


def _frame(event: str, data: dict) -> str:
    return sse_frame(event, data)


__all__ = ["router"]
