#!/usr/bin/env python
"""Rebuild the file index from the stored uploads.

Needed after changing the embedding model: vectors produced by another model
(usually another dimension) cannot be reused, so both stores must be dropped and
every file re-parsed and re-embedded.

Run it with the application stopped (they share the sqlite / LanceDB files):

    python tools/reindex_corpus.py --drop          # drop the stores, re-index all
    python tools/reindex_corpus.py                 # re-index in place

Original file names are restored before parsing, because the file storage keeps
the upload under a content hash without an extension and the reader is chosen by
the extension.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COPY_DIR = REPO_ROOT / "ktem_app_data" / "reindex_src"


def pick_index(app, index_id: int | None):
    indices = list(getattr(app.index_manager, "indices", []))
    if not indices:
        raise SystemExit("no index is configured")
    if index_id is not None:
        for index in indices:
            if getattr(index, "id", None) == index_id:
                return index
        raise SystemExit(f"index {index_id} not found")
    for index in indices:
        if type(index).__name__ == "FileIndex":
            return index
    return indices[0]


def stored_sources(index) -> list[tuple[str, str, str, str]]:
    """Return ``(source_id, name, stored_path, user_id)`` for every indexed file.

    ``Source.path`` is only the content hash; the file itself lives under the
    index' file storage directory.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from ktem.db.models import engine

    Source = index._resources["Source"]
    with Session(engine) as session:
        rows = session.execute(
            select(Source.id, Source.name, Source.path, Source.user)
        ).all()

    resolved = []
    for source_id, name, stored, user in rows:
        path = Path(stored)
        if not path.is_absolute():
            path = Path(index._fs_path) / stored
        resolved.append((source_id, name, str(path), user))
    return resolved


def index_paths(pipeline, paths: list[Path]) -> int:
    """Index ``paths`` and return the number of failures.

    ``IndexDocumentPipeline.stream`` swallows exceptions and reports them as a
    ``status: "failed"`` document on the ``index`` channel, so the stream has to
    be inspected rather than merely consumed.
    """
    failed = 0
    for document in pipeline.stream(paths, reindex=True):
        channel = getattr(document, "channel", None)
        if channel != "index":
            continue
        content = document.content if isinstance(document.content, dict) else {}
        name = content.get("file_name", "?")
        if content.get("status") == "success":
            print(f"  [ok]   {name}")
        else:
            failed += 1
            print(f"  [fail] {name}: {content.get('message', 'unknown error')}")
    return failed


def restore_copy(name: str, stored_path: str) -> Path:
    """Copy the stored upload to a path that carries the original extension."""
    COPY_DIR.mkdir(parents=True, exist_ok=True)
    target = COPY_DIR / name
    shutil.copyfile(stored_path, target)
    return target


def drop_stores(index) -> None:
    """Drop the vector and document stores so a new model can write fresh ones.

    The relation rows in the metadata database point at chunks that no longer
    exist once the stores are gone, so they are cleared too — otherwise deleting
    a file would ask the fresh store to delete ids it never had.
    """
    from ktem.components import get_docstore, get_vectorstore
    from ktem.db.models import engine
    from sqlalchemy import delete
    from sqlalchemy.orm import Session

    name = f"index_{index.id}"
    for store in (get_vectorstore(name), get_docstore(name)):
        try:
            store.drop()
        except Exception as exc:  # noqa: BLE001 - a missing store is fine
            print(f"  [warn] {type(store).__name__}.drop: {exc}")
    get_vectorstore.cache_clear()
    get_docstore.cache_clear()
    index._vs = get_vectorstore(name)
    index._docstore = get_docstore(name)
    index._resources["VectorStore"] = index._vs
    index._resources["DocStore"] = index._docstore

    with Session(engine) as session:
        session.execute(delete(index._resources["Index"]))
        session.commit()
    print(f"dropped stores and relations for {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-id", type=int, default=None)
    parser.add_argument(
        "--drop",
        action="store_true",
        help="drop the vector/document stores first (needed after a model change)",
    )
    parser.add_argument(
        "--keep-sources",
        action="store_true",
        help="keep the stored copies under ktem_app_data/reindex_src afterwards",
    )
    parser.add_argument(
        "--match",
        default=None,
        help="only re-index files whose name contains this substring",
    )
    parser.add_argument(
        "--add",
        action="append",
        default=None,
        metavar="PATH",
        help="index an extra file that is not in the index yet (repeatable)",
    )
    parser.add_argument("--user-id", default=None, help="owner for --add files")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(REPO_ROOT))
    for lib in ("libs/ktem", "libs/kotaemon"):
        sys.path.insert(0, str(REPO_ROOT / lib))
    from ktem.main import App

    app = App()
    index = pick_index(app, args.index_id)
    settings = app.default_settings.flatten()
    print(f"index: {type(index).__name__} (id={index.id})")

    sources = stored_sources(index)
    user_id = args.user_id or (sources[0][3] if sources else None)

    if args.add:
        pipeline = index.get_indexing_pipeline(settings, user_id)
        print(f"embedding: {getattr(pipeline.embedding, 'model_name', '?')}")
        failed = index_paths(pipeline, [Path(p) for p in args.add])
        print(f"done: {len(args.add) - failed} ok, {failed} failed")
        return 0 if failed == 0 else 1

    if args.match:
        sources = [s for s in sources if args.match in s[1]]
    print(f"indexed files: {len(sources)}")
    if not sources:
        print("nothing to re-index")
        return 1

    if args.drop:
        drop_stores(index)

    pipeline = index.get_indexing_pipeline(settings, user_id)
    print(f"embedding: {getattr(pipeline.embedding, 'model_name', '?')}")

    failed = 0
    for source_id, name, stored_path, owner in sources:
        path = Path(stored_path)
        if not path.exists():
            print(f"  [skip] {name}: stored file missing ({stored_path})")
            failed += 1
            continue
        copy = restore_copy(name, stored_path)
        print(f"  indexing {name} ...")
        pipeline = index.get_indexing_pipeline(settings, owner)
        failed += index_paths(pipeline, [copy])

    if not args.keep_sources:
        shutil.rmtree(COPY_DIR, ignore_errors=True)

    print(f"done: {len(sources) - failed} ok, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
