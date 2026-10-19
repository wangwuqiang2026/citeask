"""File-index operations behind ``/api/v1/files`` and ``/api/v1/groups``.

The classic file page (``ktem/index/file/ui.py``) is a Gradio page: it owns the
tables, the pipelines and the widgets. This module keeps the *application logic*
of that page — list, upload/index, delete, download, chunk preview and file
groups — in a Gradio-free service so the web API can reuse it (and the tests can
exercise it without a browser).

Two deliberate differences from the Gradio page, both documented at the call
site:

* the row set is a superset of the table columns: the classic table hides the
  internal id and does not show ``type``/``blocks``, while a JSON API needs the
  id (for follow-up calls) and the frontend wants a type label and the chunk
  count. ``tokens`` is a number here, not the table's padded text;
* the indexing progress is yielded as structured ``(event, data)`` pairs instead
  of Gradio text boxes; the API layer turns them into SSE frames.

Storage facts this module relies on (verified in the code it mirrors):

* ``Source.path`` is the *stored* name under ``FileStoragePath`` for uploads,
  and a bare content hash for URLs (no file on disk);
* chunks are the ``document`` relations of a source in the ``Index`` table, and
  the text lives in the document store;
* a private index scopes every row by ``Source.user`` / ``FileGroup.user``.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from sqlalchemy import func
from sqlmodel import Session, select

from ktem.db.engine import engine
from ktem.utils.file_profile import describe_profile
from ktem.utils.i18n import tr

logger = logging.getLogger(__name__)

#: Columns the classic table shows (``ktem/index/file/ui.py``). Kept here so the
#: parity is visible; the API adds ``file_id``/``type``/``blocks`` on top.
FILE_LIST_COLUMNS = ("name", "size", "tokens", "loader", "profile", "date_created")

#: Columns of ``GET /files``. ``file_id`` is what follow-up calls take; ``type``
#: is the extension (or ``url``), ``blocks`` is the number of chunks.
FILE_COLUMNS = (
    "file_id",
    "name",
    "type",
    "size",
    "blocks",
    "loader",
    "profile",
    "date_created",
    "tokens",
)

#: The chunk types counted for the chunk drawer.
CHUNK_TYPES = ("text", "table", "image", "thumbnail")

MAX_ERROR_LENGTH = 60


class FileService:
    """Read and mutate the file index of one application instance."""

    def __init__(self, app):
        self._app = app

    # ------------------------------------------------------------------ index
    @staticmethod
    def _is_file_index(index: Any) -> bool:
        resources = getattr(index, "_resources", None) or {}
        return "Source" in resources and "Index" in resources

    def file_indices(self) -> list[Any]:
        return [
            index
            for index in getattr(self._app.index_manager, "indices", [])
            if self._is_file_index(index)
        ]

    def resolve_index(self, index_id: Optional[int] = None):
        """The requested file index, or the first one.

        Raises:
            ValueError: no file index is configured.
            KeyError: ``index_id`` does not name a file index.
        """
        indices = self.file_indices()
        if not indices:
            raise ValueError("尚未配置文件索引")
        if index_id is None:
            return indices[0]
        for index in indices:
            if str(index.id) == str(index_id):
                return index
        raise KeyError("索引不存在")

    # -------------------------------------------------------------- locations
    def _source(self, index, file_id: str, user: dict):
        Source = index._resources["Source"]
        with Session(engine) as session:
            row = session.execute(select(Source).where(Source.id == file_id)).first()
        if row is None:
            raise KeyError("文件不存在")
        source = row[0]
        if index.config.get("private", False) and str(source.user) != str(
            user.get("id")
        ):
            raise PermissionError("无权访问该文件")
        return source

    def locate(self, file_id: str, user: dict, index_id: Optional[int] = None):
        """Find ``(index, source)`` for an id without knowing its index.

        The file routes do not carry an index id (the id is a UUID chosen by the
        store), so delete/chunks/download/reindex look it up across the file
        indices.
        """
        candidates = (
            [self.resolve_index(index_id)]
            if index_id is not None
            else self.file_indices()
        )
        for index in candidates:
            try:
                return index, self._source(index, file_id, user)
            except KeyError:
                continue
        raise KeyError("文件不存在")

    def _stored_path(self, index, source) -> Optional[Path]:
        stored = str(source.path or "")
        if not stored:
            return None
        path = Path(stored)
        if not path.is_absolute():
            path = Path(index._resources["FileStoragePath"]) / path
        return path if path.exists() else None

    @staticmethod
    def _user_scope(index, statement, model, user: dict):
        if index.config.get("private", False):
            return statement.where(model.user == user.get("id"))
        return statement

    # ------------------------------------------------------------------- read
    def list_files(
        self, index_id: Optional[int], user: dict, query: str = ""
    ) -> dict:
        index = self.resolve_index(index_id)
        Source = index._resources["Source"]
        Index = index._resources["Index"]

        pattern = (query or "").strip()
        statement = self._user_scope(index, select(Source), Source, user)
        if pattern:
            # escape LIKE metacharacters: the input is a literal substring
            escaped = (
                pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            statement = statement.where(Source.name.ilike(f"%{escaped}%", escape="\\"))

        with Session(engine) as session:
            sources = [row[0] for row in session.execute(statement).all()]
            blocks = {
                source_id: count
                for source_id, count in session.execute(
                    select(Index.source_id, func.count())
                    .where(Index.relation_type == "document")
                    .group_by(Index.source_id)
                ).all()
            }

        rows = [
            self._row(source, int(blocks.get(source.id, 0))) for source in sources
        ]
        return {
            "index_id": index.id,
            "columns": list(FILE_COLUMNS),
            "rows": rows,
        }

    @staticmethod
    def _format_size(num: Any, suffix: str = "B") -> Any:
        """``1.5 MB`` from a byte count (mirrors the classic table's helper).

        The padding ``:{width}`` of the Gradio helper is dropped: it aligns a
        monospace table, and in JSON it would only add leading spaces.
        """
        try:
            value = float(num)
        except (TypeError, ValueError):
            return num
        for unit in ("", "K", "M", "G", "T", "P", "E", "Z"):
            if abs(value) < 1024.0:
                return f"{value:.0f}{unit}{suffix}"
            value /= 1024.0
        return f"{value:.0f}Yi{suffix}"

    @staticmethod
    def _describe_loader(note: Any) -> str:
        """The ``loader`` cell: what parsed the file, or why it failed."""
        note = note if isinstance(note, dict) else {}
        error = note.get("error")
        if error:
            text = str(error)
            if len(text) > MAX_ERROR_LENGTH:
                text = text[: MAX_ERROR_LENGTH - 3] + "..."
            return f"\u26a0 {text}"
        return note.get("loader", "-")

    def _row(self, source, blocks: int) -> dict:
        note = source.note if isinstance(source.note, dict) else {}
        name = str(source.name or "")
        raw_tokens = note.get("tokens", "-")
        try:
            tokens: Any = int(raw_tokens)
        except (TypeError, ValueError):
            tokens = raw_tokens if isinstance(raw_tokens, str) else "-"
        return {
            "file_id": source.id,
            "name": name,
            "type": self._file_type(name),
            "size": self._format_size(source.size),
            "blocks": blocks,
            "loader": self._describe_loader(note),
            "profile": describe_profile(note, limit=45, suffix=""),
            "date_created": (
                source.date_created.strftime("%Y-%m-%d %H:%M:%S")
                if source.date_created
                else ""
            ),
            # a count is more useful as a number than as the table's padded text
            "tokens": tokens,
        }

    @staticmethod
    def _file_type(name: str) -> str:
        if name.startswith(("http://", "https://")):
            return "url"
        suffix = Path(name).suffix.lstrip(".").lower()
        return suffix or "-"

    # ---------------------------------------------------------------- chunks
    def chunks(
        self, file_id: str, user: dict, type_filter: str = "all"
    ) -> dict:
        index, source = self.locate(file_id, user)
        Index = index._resources["Index"]

        with Session(engine) as session:
            doc_ids = [
                row[0]
                for row in session.execute(
                    select(Index.target_id).where(
                        Index.source_id == source.id,
                        Index.relation_type == "document",
                    )
                ).all()
            ]

        docs: list[Any] = []
        if doc_ids and getattr(index, "_docstore", None) is not None:
            docs = list(index._docstore.get(doc_ids) or [])
        # missing page labels sort last; they are serialized as ``null`` rather
        # than ``Infinity``, which would not be valid JSON
        docs.sort(key=lambda doc: (self._page_of(doc) is None, self._page_of(doc) or 0))

        counts: dict[str, int] = {kind: 0 for kind in CHUNK_TYPES}
        for doc in docs:
            kind = self._type_of(doc)
            counts[kind] = counts.get(kind, 0) + 1

        want = (type_filter or "all").strip().lower()
        selected = (
            docs if want == "all" else [d for d in docs if self._type_of(d) == want]
        )

        return {
            "file_id": source.id,
            "name": str(source.name or ""),
            "header": tr("{} chunks").format(len(selected)),
            "counts": counts,
            "chunks": [
                {
                    "index": position + 1,
                    "page": self._page_of(doc),
                    "type": self._type_of(doc),
                    "text": doc.text,
                    # the frontend renders the text itself (markdown/tables), so no
                    # server-side HTML is needed; the key is kept for parity
                    "html": "",
                }
                for position, doc in enumerate(selected)
            ],
        }

    @staticmethod
    def _type_of(doc) -> str:
        metadata = getattr(doc, "metadata", None) or {}
        return str(metadata.get("type") or "text").lower()

    @staticmethod
    def _page_of(doc) -> Optional[int]:
        metadata = getattr(doc, "metadata", None) or {}
        try:
            return int(metadata.get("page_label"))
        except (TypeError, ValueError):
            return None

    # ---------------------------------------------------------------- delete
    def delete_file(self, file_id: str, user: dict) -> dict:
        index, source = self.locate(file_id, user)
        Index = index._resources["Index"]
        Source = index._resources["Source"]

        vs_ids: list[str] = []
        ds_ids: list[str] = []
        with Session(engine) as session:
            relations = session.execute(
                select(Index).where(Index.source_id == source.id)
            ).all()
            for (relation,) in relations:
                if relation.relation_type == "vector":
                    vs_ids.append(relation.target_id)
                elif relation.relation_type == "document":
                    ds_ids.append(relation.target_id)
                session.delete(relation)
            row = session.execute(
                select(Source).where(Source.id == source.id)
            ).first()
            if row is not None:
                session.delete(row[0])
            session.commit()

        self._delete_embeddings(index, vs_ids, ds_ids)

        stored = self._stored_path(index, source)
        if stored is not None:
            try:
                stored.unlink(missing_ok=True)
            except OSError as exc:  # a read-only store must not fail the deletion
                logger.warning("could not remove stored file %s: %s", stored, exc)

        return {"ok": True, "file_id": source.id, "name": str(source.name or "")}

    @staticmethod
    def _delete_embeddings(index, vs_ids: Iterable[str], ds_ids: Iterable[str]):
        vectorstore = getattr(index, "_vs", None)
        docstore = getattr(index, "_docstore", None)
        if vs_ids and vectorstore is not None:
            try:
                vectorstore.delete(list(vs_ids))
            except Exception:  # noqa: BLE001 - the rows are already gone
                logger.exception("could not delete vectors of a removed file")
        if ds_ids and docstore is not None:
            try:
                docstore.delete(list(ds_ids))
            except Exception:  # noqa: BLE001
                logger.exception("could not delete documents of a removed file")

    # -------------------------------------------------------------- download
    def download(self, file_id: str, user: dict) -> tuple[Path, str]:
        index, source = self.locate(file_id, user)
        if str(source.name or "").startswith(("http://", "https://")):
            raise ValueError("网页链接没有可下载的原始文件")
        stored = self._stored_path(index, source)
        if stored is None:
            raise KeyError("原始文件不存在或已被删除")
        return stored, Path(str(source.name)).name or stored.name

    # ---------------------------------------------------------------- groups
    def list_groups(self, index_id: Optional[int], user: dict) -> dict:
        index = self.resolve_index(index_id)
        FileGroup = index._resources["FileGroup"]
        statement = self._user_scope(index, select(FileGroup), FileGroup, user)
        with Session(engine) as session:
            groups = [row[0] for row in session.execute(statement).all()]
        return {
            "index_id": index.id,
            "items": [self._group_item(group) for group in groups],
        }

    def locate_group(self, group_id: str, user: dict, index_id: Optional[int] = None):
        candidates = (
            [self.resolve_index(index_id)]
            if index_id is not None
            else self.file_indices()
        )
        for index in candidates:
            FileGroup = index._resources["FileGroup"]
            with Session(engine) as session:
                row = session.execute(
                    select(FileGroup).where(FileGroup.id == group_id)
                ).first()
            if row is None:
                continue
            group = row[0]
            if index.config.get("private", False) and str(group.user) != str(
                user.get("id")
            ):
                raise PermissionError("无权访问该分组")
            return index, group
        raise KeyError("分组不存在")

    @staticmethod
    def _group_item(group) -> dict:
        data = group.data if isinstance(group.data, dict) else {}
        return {
            "id": group.id,
            "name": group.name,
            "files": list(data.get("files", []) or []),
            "date_created": (
                group.date_created.strftime("%Y-%m-%d %H:%M:%S")
                if group.date_created
                else ""
            ),
        }

    @staticmethod
    def _clean_name(name: Any) -> str:
        text = str(name or "").strip()
        if not text:
            raise ValueError("分组名不能为空")
        return text

    @staticmethod
    def _clean_files(files: Any) -> list[str]:
        if files is None:
            return []
        if not isinstance(files, (list, tuple)):
            raise ValueError("文件列表格式无效")
        cleaned: list[str] = []
        for item in files:
            text = str(item)
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    def create_group(self, index_id, user: dict, name: str, files: Any) -> dict:
        index = self.resolve_index(index_id)
        FileGroup = index._resources["FileGroup"]
        cleaned_name = self._clean_name(name)
        cleaned_files = self._clean_files(files)

        with Session(engine) as session:
            duplicate = session.execute(
                select(FileGroup).where(
                    FileGroup.name == cleaned_name,
                    FileGroup.user == user.get("id"),
                )
            ).first()
            if duplicate is not None:
                raise ValueError(f"分组 {cleaned_name} 已存在")
            group = FileGroup(
                name=cleaned_name,
                user=user.get("id"),
                data={"files": cleaned_files},
            )
            session.add(group)
            session.commit()
            session.refresh(group)
            item = self._group_item(group)

        return {"index_id": index.id, "item": item}

    def update_group(
        self,
        group_id: str,
        user: dict,
        name: Optional[str] = None,
        files: Any = None,
        index_id: Optional[int] = None,
    ) -> dict:
        index, group = self.locate_group(group_id, user, index_id)
        FileGroup = index._resources["FileGroup"]

        with Session(engine) as session:
            row = session.execute(
                select(FileGroup).where(FileGroup.id == group.id)
            ).first()
            if row is None:
                raise KeyError("分组不存在")
            item = row[0]

            if name is not None:
                cleaned_name = self._clean_name(name)
                duplicate = session.execute(
                    select(FileGroup).where(
                        FileGroup.name == cleaned_name,
                        FileGroup.user == item.user,
                        FileGroup.id != item.id,
                    )
                ).first()
                if duplicate is not None:
                    raise ValueError(f"分组 {cleaned_name} 已存在")
                item.name = cleaned_name
            if files is not None:
                data = dict(item.data or {})
                data["files"] = self._clean_files(files)
                item.data = data
            session.add(item)
            session.commit()
            session.refresh(item)
            return {"index_id": index.id, "item": self._group_item(item)}

    def delete_group(self, group_id: str, user: dict, index_id=None) -> dict:
        index, group = self.locate_group(group_id, user, index_id)
        FileGroup = index._resources["FileGroup"]
        with Session(engine) as session:
            row = session.execute(
                select(FileGroup).where(FileGroup.id == group.id)
            ).first()
            if row is None:
                raise KeyError("分组不存在")
            session.delete(row[0])
            session.commit()
        return {"ok": True, "id": group.id}

    # ---------------------------------------------------------------- upload
    @staticmethod
    def upload_tempdir() -> Path:
        """A scratch directory for the current upload/reindex request."""
        return Path(tempfile.mkdtemp(prefix="ktem-api-files-"))

    def settings_for(self, user: dict) -> dict:
        """The effective settings of ``user`` (defaults overlaid with the row)."""
        try:
            from ktem.services.settings import SettingsService

            return SettingsService(self._app).load(user.get("id"))
        except Exception:  # noqa: BLE001 - uploads must not depend on settings
            logger.exception("could not load the user settings; using defaults")
            try:
                return dict(self._app.default_settings.flatten())
            except Exception:  # noqa: BLE001
                return {}

    def _validate_files(self, index, paths: list[Path]) -> list[str]:
        """Size and count limits of the index (mirrors the classic page)."""
        errors: list[str] = []
        max_size = index.config.get("max_file_size", 0)
        if max_size:
            too_big = [
                path.name for path in paths if path.stat().st_size > max_size * 1e6
            ]
            if too_big:
                text = ", ".join(too_big)
                if len(text) > 60:
                    text = text[:55] + "..."
                errors.append(f"超过单文件大小上限（{max_size} MB）：{text}")

        max_files = index.config.get("max_number_of_files", 0)
        if max_files:
            Source = index._resources["Source"]
            with Session(engine) as session:
                current = len(session.execute(select(Source.id)).all())
            if len(paths) + current > max_files:
                errors.append(f"超过索引文件数量上限（{max_files}）")
        return errors

    @staticmethod
    def _validate_urls(urls: Iterable[str]) -> list[str]:
        errors: list[str] = []
        for url in urls:
            if not url.startswith(("http://", "https://")):
                errors.append(f"无效的网址：{url}")
        return errors

    def validate_upload(
        self, index, paths: Iterable[Path], urls: Iterable[str]
    ) -> list[str]:
        """Everything wrong with this request, in Chinese (empty ⇒ valid)."""
        path_list = [Path(p) for p in paths]
        url_list = [u for u in urls if u]
        errors = self._validate_urls(url_list)
        errors.extend(self._validate_files(index, path_list))
        return errors

    def prepare_reindex(
        self, file_id: str, user: dict, work_dir: Optional[Path] = None
    ):
        """Copy the stored upload to a scratch dir under its original name.

        The store keeps uploads under their content hash; the reader is chosen by
        the extension and the source row takes its name from the file name, so a
        reindex has to restore the original name first (the same trick as the
        startup repair in ``ktem.index.file.repair``).
        """
        index, source = self.locate(file_id, user)
        if str(source.name or "").startswith(("http://", "https://")):
            raise ValueError("网页链接不支持重建索引")
        stored = self._stored_path(index, source)
        if stored is None:
            raise KeyError("原始文件不存在，无法重建索引")

        directory = Path(work_dir or self.upload_tempdir())
        directory.mkdir(parents=True, exist_ok=True)
        copy = directory / (Path(str(source.name)).name or stored.name)
        try:
            shutil.copyfile(stored, copy)
        except Exception:  # noqa: BLE001 - do not leak the scratch directory
            shutil.rmtree(directory, ignore_errors=True)
            raise
        return index, copy, directory

    def stream_paths(
        self,
        index,
        user: dict,
        paths: Iterable[Path],
        urls: Iterable[str] = (),
        reindex: bool = False,
        cleanup_dir: Optional[Path] = None,
    ) -> Iterator[tuple[str, dict]]:
        """Yield ``(event, data)`` for one indexing run.

        Events: ``progress`` (one line per file), ``done`` (ids + errors) and
        ``error`` (a fatal problem before/while indexing). The generator is
        synchronous on purpose: Starlette runs a sync iterator in a worker
        thread, which keeps the blocking readers and the embedding calls off the
        event loop.
        """
        url_list = [url for url in urls if url]
        path_list = [Path(path) for path in paths]
        try:
            errors = self.validate_upload(index, path_list, url_list)
            if errors:
                yield ("error", {"message": "；".join(errors)})
                return

            items: list[Any] = [str(path) for path in path_list] + url_list
            if not items:
                yield ("error", {"message": "没有选择文件或网址"})
                return

            pipeline = index.get_indexing_pipeline(
                self.settings_for(user), user.get("id")
            )
            stream = pipeline.stream(items, reindex=reindex)

            ids: list[Any] = []
            failures: list[Any] = []
            while True:
                try:
                    event = next(stream)
                except StopIteration as stop:
                    ids, failures, _docs = stop.value
                    break

                content = getattr(event, "content", None)
                if getattr(event, "channel", None) != "index" or not isinstance(
                    content, dict
                ):
                    continue  # debug lines are not part of the SSE contract
                name = content.get("file_name", "")
                if content.get("status") == "success":
                    yield ("progress", {"line": f"\u2705 | {name}"})
                elif content.get("status") == "failed":
                    yield (
                        "progress",
                        {"line": f"\u274c | {name}: {content.get('message', '')}"},
                    )

            yield (
                "done",
                {
                    "ids": [item for item in ids if item],
                    "errors": [str(item) for item in failures if item],
                },
            )
        except Exception as exc:  # noqa: BLE001 - reported as an SSE error frame
            logger.exception("indexing failed")
            yield ("error", {"message": f"索引失败：{exc}"})
        finally:
            if cleanup_dir is not None:
                shutil.rmtree(cleanup_dir, ignore_errors=True)


def sse_frame(event: str, data: dict) -> str:
    """One SSE frame; ``ensure_ascii=False`` keeps Chinese/file names readable."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


__all__ = [
    "CHUNK_TYPES",
    "FILE_COLUMNS",
    "FILE_LIST_COLUMNS",
    "FileService",
    "sse_frame",
]
