"""Rebuild an index when the embedding model changes (MODIFICATIONS §5.36).

Vectors produced by one embedding model cannot be reused by another: the
dimension and the meaning of the coordinates both change. Switching therefore
means dropping the vector and document stores and re-parsing every stored upload
with the new model. The work runs in a background thread because it is
minutes-long for a real corpus and the HTTP request must not block on it.
"""

from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ktem.components import get_docstore, get_vectorstore
from ktem.db.models import engine

#: Called with keyword changes of the job state (``state``/``total``/``done``/…).
Progress = Callable[..., None]


def stored_sources(index) -> list[dict]:
    """Every indexed file of ``index``, with the owner it was indexed for.

    ``Source.path`` is the stored upload name (a content hash without extension),
    relative to the index file storage directory; the reader is chosen by the
    extension, so re-indexing needs a copy under the original name.
    """
    Source = index._resources["Source"]
    with Session(engine) as session:
        rows = session.execute(
            select(Source.id, Source.name, Source.path, Source.user)
        ).all()

    sources = []
    for source_id, name, stored, user in rows:
        path = Path(str(stored))
        if not path.is_absolute():
            path = Path(index._fs_path) / path
        sources.append({"id": source_id, "name": name, "path": path, "user": user})
    return sources


def drop_stores(index) -> None:
    """Drop the stores and the chunk relations, then attach fresh empty ones.

    The relation rows point at chunks that no longer exist once the stores are
    gone, so they are cleared too; otherwise deleting a file would ask the fresh
    store to delete ids it never had.
    """
    name = f"index_{index.id}"
    for factory in (get_vectorstore, get_docstore):
        try:
            factory(name).drop()
        except Exception:  # noqa: BLE001 - a missing (never created) store is fine
            pass
    get_vectorstore.cache_clear()
    get_docstore.cache_clear()

    index._vs = get_vectorstore(name)
    index._docstore = get_docstore(name)
    index._resources["VectorStore"] = index._vs
    index._resources["DocStore"] = index._docstore

    with Session(engine) as session:
        session.execute(delete(index._resources["Index"]))
        session.commit()


def _is_url(name: Any) -> bool:
    return str(name or "").startswith(("http://", "https://"))


def _restore_stored_copy(index, source: dict, target: Path) -> None:
    """Put the uploaded bytes back when a failed reindex removed the store copy.

    The pipeline deletes the old row (and its stored copy) before parsing, then
    stores the scratch copy again. If it failed in between, the user's upload is
    gone; the scratch copy is still the same bytes, so restore it (§5.36).
    """
    stored = Path(str(source["path"]))
    if not stored.is_absolute():
        stored = Path(index._fs_path) / stored
    if stored.exists() or not target.exists():
        return
    try:
        stored.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target, stored)
    except OSError:  # noqa: BLE001 - preserving the rest of the rebuild matters more
        pass


def reindex_index(
    index,
    embedding_name: str,
    settings: dict,
    report: Progress,
    base: dict | None = None,
) -> tuple:
    """Re-index every file of one index; returns ``(done, failed, skipped)``.

    ``base`` carries the counters of the indices already rebuilt, so the caller
    can report one continuous progress line. A web link has no stored bytes to
    re-parse, so it is counted as skipped rather than failed (§5.36).
    """
    done = failed = skipped = 0
    already = dict(base or {"done": 0, "failed": 0, "skipped": 0})

    def progress(**changes) -> None:
        report(
            done=already["done"] + done,
            failed=already["failed"] + failed,
            skipped=already["skipped"] + skipped,
            embedding=embedding_name,
            **changes,
        )

    scratch = Path(tempfile.mkdtemp(prefix="ktem-reindex-"))
    try:
        for source in stored_sources(index):
            if _is_url(source["name"]):
                skipped += 1
                progress(message=f"跳过 {source['name']}：网页链接无法用新模型重建")
                continue

            name = Path(str(source["name"])).name or f"source-{source['id']}"
            target = scratch / name
            try:
                shutil.copyfile(source["path"], target)
            except Exception:  # noqa: BLE001 - one unreadable file must not stop
                failed += 1
                progress(message=f"跳过 {source['name']}：原始文件不存在")
                continue

            pipeline = index.get_indexing_pipeline(settings, source["user"])
            succeeded = False
            try:
                # keep_on_failure: the reindex path deletes the old row and copy
                # before parsing, so on failure the file must keep the row this
                # attempt created instead of losing the upload entirely (§5.36).
                for document in pipeline.stream(
                    [target], reindex=True, keep_on_failure=True
                ):
                    content = getattr(document, "content", None)
                    if getattr(document, "channel", None) != "index" or not isinstance(
                        content, dict
                    ):
                        continue  # debug lines are not part of the contract
                    if content.get("status") == "success":
                        succeeded = True
                    elif content.get("status") == "failed":
                        failed += 1
                        succeeded = False
                        break
            except Exception as exc:  # noqa: BLE001 - keep going with the next file
                failed += 1
                succeeded = False
                progress(message=f"{source['name']} 重建失败：{exc}")
            finally:
                _restore_stored_copy(index, source, target)
                target.unlink(missing_ok=True)

            if succeeded:
                done += 1
            progress()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return done, failed, skipped


def rebuild_all(app, embedding_name: str, report: Progress) -> dict:
    """Point every index at ``embedding_name`` and rebuild it.

    Returns ``{"total", "done", "failed", "skipped"}``; the caller owns the job
    state. ``skipped`` counts web links, which cannot be rebuilt.
    """
    from ktem.embeddings.manager import embedding_models_manager

    manager = app.index_manager
    indices = list(manager.indices)

    total = 0
    for index in indices:
        total += len(stored_sources(index))
    report(
        state="running",
        embedding=embedding_name,
        total=total,
        done=0,
        failed=0,
        skipped=0,
        message=f"正在用 {embedding_name} 重建索引",
    )

    spec = (embedding_models_manager.info().get(embedding_name) or {}).get("spec")
    if not spec:
        raise ValueError(f"未知的模型：{embedding_name}")
    embedding_models_manager.update(embedding_name, spec=spec, default=True)

    settings = app.default_settings.flatten()
    done = failed = skipped = 0
    for index in indices:
        config = dict(index.config or {})
        config["embedding"] = embedding_name
        manager.update_index(index.id, index.name, config)
        drop_stores(index)
        file_done, file_failed, file_skipped = reindex_index(
            index,
            embedding_name,
            settings,
            report,
            base={"done": done, "failed": failed, "skipped": skipped},
        )
        done += file_done
        failed += file_failed
        skipped += file_skipped
    return {"total": total, "done": done, "failed": failed, "skipped": skipped}


class ReindexJob:
    """The single background embedding rebuild the web UI polls."""

    def __init__(self, rebuild: Callable[..., dict] = rebuild_all):
        self._rebuild = rebuild
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {
            "state": "idle",
            "embedding": "",
            "total": 0,
            "done": 0,
            "failed": 0,
            "skipped": 0,
            "message": "",
        }

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._state)

    def start(self, app, embedding_name: str) -> dict:
        with self._lock:
            if self._state["state"] == "running":
                raise RuntimeError("已有索引重建任务在运行，请等待它结束")
            self._state = {
                "state": "running",
                "embedding": embedding_name,
                "total": 0,
                "done": 0,
                "failed": 0,
                "skipped": 0,
                "message": "正在准备重建索引",
            }
        threading.Thread(
            target=self._run,
            args=(app, embedding_name),
            name="embedding-reindex",
            daemon=True,
        ).start()
        return self.snapshot()

    def _run(self, app, embedding_name: str) -> None:
        def report(**changes) -> None:
            with self._lock:
                self._state.update(changes)

        try:
            result = self._rebuild(app, embedding_name, report)
        except Exception as exc:  # noqa: BLE001 - surfaced on the page
            report(state="error", message=f"重建失败：{exc}")
            return

        done = int(result.get("done", 0))
        failed = int(result.get("failed", 0))
        skipped = int(result.get("skipped", 0))
        message = f"索引已用 {embedding_name} 重建完成（{done}/{result.get('total', done)} 个文件）"
        if failed:
            message += f"；失败 {failed} 个文件"
        if skipped:
            message += f"；跳过 {skipped} 个网页链接"
        if failed or skipped:
            detail = self.snapshot()["message"]
            if "失败" in detail or "跳过" in detail:
                message += f"（{detail}）"
        report(
            state="done",
            done=done,
            failed=failed,
            skipped=skipped,
            total=result.get("total", done),
            message=message,
        )


#: The job the resources page triggers and polls.
reindex_job = ReindexJob()

__all__ = [
    "ReindexJob",
    "drop_stores",
    "rebuild_all",
    "reindex_index",
    "reindex_job",
    "stored_sources",
]
