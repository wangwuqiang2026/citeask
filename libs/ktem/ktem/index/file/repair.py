"""Re-parse files that are listed in the index but carry no chunks.

Such rows are the tail of every "the app cannot read my file" report this project
has had: the parse failed (missing system library, missing optional dependency, a
reader that could not handle the format), the ``Source`` row stayed behind, so the
file list showed a file that retrieval could not see and questions about it
answered ``No evidence found.`` — see MODIFICATIONS §2.7 (``.docx``), §2.9
(``.xls``) and §2.10 for the class of bug.

Uploads no longer leave such rows behind (``BaseFileIndexIndexing.
_handle_failed_indexing``), and this module heals the ones that already exist: a
file whose reader was fixed is re-parsed on the next start instead of waiting for
somebody to rebuild the index by hand.
"""

from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from theflow.settings import settings as flowsettings

from ktem.db.models import engine

logger = logging.getLogger(__name__)

#: A file whose retry fails as well is attempted again on the next start, but only
#: this many times: without a cap, a permanently broken reader would re-parse and
#: re-embed the same file at every boot.
MAX_ATTEMPTS = 3

PipelineFactory = Callable[[Any, dict[str, Any], str], Any]


def find_orphans(index) -> list[dict[str, Any]]:
    """Return the sources of ``index`` that cannot be retrieved.

    Retrieval goes through the vector store, so a source is only usable when it has
    ``vector`` relations. A run that fails while embedding leaves every ``document``
    relation behind and no vector at all — that file is listed, looks indexed (10k
    chunks), and still answers nothing, so "no documents" is the wrong test.

    Returns:
        one dict per orphan: ``id``, ``name``, ``path`` (as stored),
        ``user`` and ``note`` (a copy, including the repair bookkeeping).
    """
    Source = index._resources["Source"]
    Index = index._resources["Index"]
    with Session(engine) as session:
        indexed = select(Index.source_id).where(Index.relation_type == "vector")
        rows = session.execute(
            select(
                Source.id,
                Source.name,
                Source.path,
                Source.user,
                Source.note,
            ).where(~Source.id.in_(indexed))
        ).all()

    return [
        {
            "id": source_id,
            "name": name,
            "path": path,
            "user": user,
            "note": dict(note or {}),
        }
        for source_id, name, path, user, note in rows
    ]


def _default_pipeline_factory(index, settings: dict[str, Any], user_id: str):
    """Build the indexing pipeline the same way the upload path does."""
    return index.get_indexing_pipeline(settings, user_id)


def _stored_file(index, stored: str) -> Optional[Path]:
    """Resolve the stored upload of a source (kept under its content hash)."""
    path = Path(stored)
    if not path.is_absolute():
        path = Path(index._resources["FileStoragePath"]) / path
    return path if path.exists() else None


def _current_source_id(index, orphan: dict[str, Any]) -> Optional[str]:
    """Resolve the source row of an orphan *now*.

    A retry re-creates the row (``reindex=True`` deletes and stores again), so the id
    collected before the retry is stale — writing the failure against it silently
    loses the attempt counter, and the next start retries forever.
    """
    Source = index._resources["Source"]
    with Session(engine) as session:
        rows = session.execute(
            select(Source.id).where(Source.name == orphan["name"])
        ).all()
    ids = [row[0] for row in rows]
    if not ids:
        return None
    return orphan["id"] if orphan["id"] in ids else ids[0]


def _record_attempt(index, orphan: dict[str, Any], error: Optional[str]) -> None:
    """Remember how often this file was tried, and why it failed.

    ``repair_attempts`` keeps :data:`MAX_ATTEMPTS` meaningful across restarts, and
    ``error`` is what the file list shows in the ``loader`` column, so a file that
    still cannot be parsed says so instead of silently looking fine.
    """
    source_id = _current_source_id(index, orphan)
    if source_id is None:
        return

    Source = index._resources["Source"]
    with Session(engine) as session:
        row = session.execute(select(Source).where(Source.id == source_id)).first()
        if row is None:
            return
        item = row[0]
        note = dict(item.note or {})
        note["repair_attempts"] = int(note.get("repair_attempts", 0)) + 1
        if error:
            note["error"] = error
        else:
            note.pop("error", None)
        item.note = note
        session.add(item)
        session.commit()


def repair_orphans(
    index,
    settings: dict[str, Any],
    *,
    restore_dir: Optional[Path] = None,
    pipeline_factory: Optional[PipelineFactory] = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> dict[str, list[str]]:
    """Re-parse every file of ``index`` that has no chunks.

    Args:
        index: the file index
        settings: the flattened app settings (``index.options.<id>.*``)
        restore_dir: where the stored copies are given their original name back
            (the reader is chosen by the extension, the store keeps a bare hash).
            Defaults to ``<KH_APP_DATA_DIR>/repair_src``.
        pipeline_factory: override for the pipeline builder (used by the tests)
        max_attempts: stop retrying a file after this many failed attempts

    Returns:
        ``{"repaired": [...], "failed": [...], "skipped": [...]}`` source names.
    """
    result: dict[str, list[str]] = {"repaired": [], "failed": [], "skipped": []}

    orphans = find_orphans(index)
    if not orphans:
        return result

    build_pipeline = pipeline_factory or _default_pipeline_factory
    work_dir = Path(restore_dir or (Path(flowsettings.KH_APP_DATA_DIR) / "repair_src"))

    for orphan in orphans:
        name = orphan["name"]
        attempts = int(orphan["note"].get("repair_attempts", 0))
        if attempts >= max_attempts:
            logger.warning(
                "skipping repair of %s: %s failed attempts already", name, attempts
            )
            result["skipped"].append(name)
            continue

        stored = _stored_file(index, orphan["path"])
        if stored is None:
            # nothing to parse: the upload itself is gone, tell the user why the
            # file is listed but never answers anything
            _record_attempt(index, orphan, "stored file is missing")
            result["failed"].append(name)
            continue

        work_dir.mkdir(parents=True, exist_ok=True)
        copy = work_dir / Path(name).name
        shutil.copyfile(stored, copy)

        error: Optional[str] = None
        try:
            pipeline = build_pipeline(index, settings, orphan["user"])
            for event in pipeline.stream(copy, reindex=True, keep_on_failure=True):
                content = getattr(event, "content", None)
                if not isinstance(content, dict) or content.get("status") != "failed":
                    continue
                error = str(content.get("message", "indexing failed"))
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the rest
            error = f"{type(exc).__name__}: {exc}"
            logger.exception("repair of %s raised", name)

        if error is None:
            logger.info("repaired %s", name)
            result["repaired"].append(name)
        else:
            logger.warning("repair of %s failed: %s", name, error)
            _record_attempt(index, orphan, error)
            result["failed"].append(name)

    shutil.rmtree(work_dir, ignore_errors=True)
    return result


def schedule_repair(
    index,
    settings: dict[str, Any],
    *,
    restore_dir: Optional[Path] = None,
) -> Optional[threading.Thread]:
    """Run :func:`repair_orphans` in a daemon thread.

    Re-parsing re-embeds the whole file, which is much too slow to hold the UI back
    at startup, and the result only matters when somebody asks about that file.
    """
    if not find_orphans(index):
        return None

    def _run() -> None:
        try:
            outcome = repair_orphans(index, settings, restore_dir=restore_dir)
        except Exception:  # noqa: BLE001 - a failed repair must not kill the app
            logger.exception("orphan repair for index %s failed", index.name)
            return
        logger.info(
            "orphan repair for index %s: %s repaired, %s failed, %s skipped",
            index.name,
            len(outcome["repaired"]),
            len(outcome["failed"]),
            len(outcome["skipped"]),
        )

    thread = threading.Thread(
        target=_run, name=f"orphan-repair-{index.id}", daemon=True
    )
    thread.start()
    return thread
