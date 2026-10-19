"""Tests for the file-domain web API (``ktem/api/files.py``).

The API is exercised through ``fastapi.testclient`` against a throw-away SQLite
file, so the repository's own database is never written to. The Gradio page is
not imported at all: the service under test is the Gradio-free one, which is the
point of the migration.

What is covered (per the M2 contract):

* anonymous requests are rejected with 401;
* ``GET /files`` returns the column/row shape and honours the name filter;
* ``GET /files/{id}/chunks`` returns counts/chunks and 404s for unknown ids;
* delete removes the rows, the embeddings and the stored upload;
* download serves the original bytes and 404s when the copy is gone;
* groups CRUD, including the duplicate-name error;
* the SSE contract of the upload route without touching an LLM/embedding
  (an invalid URL is reported as an ``error`` frame).
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlmodel import Session, select

import ktem.index.file.index as file_index_module
import ktem.services.files as files_service
import ktem.services.settings as settings_service
from ktem.api.deps import current_user, get_app
from ktem.api.files import router
from ktem.db.models import Settings

USER = {"id": "u1", "username": "tester", "admin": True}
OTHER = {"id": "u2", "username": "other", "admin": False}


class FakeVectorStore:
    def __init__(self):
        self.deleted: list[str] = []

    def delete(self, ids):
        self.deleted.extend(list(ids))


class FakeDocumentStore:
    def __init__(self):
        self.docs: dict[str, object] = {}
        self.deleted: list[str] = []

    def get(self, ids):
        return [self.docs[i] for i in ids if i in self.docs]

    def delete(self, ids):
        self.deleted.extend(list(ids))


class FakeDefaultSettings:
    def flatten(self) -> dict:
        return {"index.options.1.reader_mode": "default"}


class FakeIndexManager:
    def __init__(self, index):
        self.indices = [index]


class FakeApp:
    """The smallest ``ktem.app.BaseApp`` surface the service uses."""

    app_name = "citeask"
    app_version = "test"
    f_user_management = True

    def __init__(self, index):
        self.default_settings = FakeDefaultSettings()
        self.index_manager = FakeIndexManager(index)


class Env(SimpleNamespace):
    """Everything a test needs: the index, its stores and a client factory."""

    def client(self, user=USER) -> TestClient:
        api = FastAPI()
        api.state.ktem_app = self.app
        api.include_router(router)
        api.dependency_overrides[get_app] = lambda: self.app
        if user is not None:
            api.dependency_overrides[current_user] = lambda: user
        return TestClient(api)

    def stored_name(self, name: str) -> str:
        """A stored-file name that no other test (or run) can collide with."""
        return f"{self.token}-{name}"

    def write_stored(self, name: str, payload: bytes) -> str:
        """Write a stored upload under the index's storage path; return its name."""
        target = self.index._resources["FileStoragePath"] / self.stored_name(name)
        target.write_bytes(payload)
        return self.stored_name(name)

    def seed_source(self, name="a.pdf", size=2048, note=None, path=None) -> str:
        Source = self.index._resources["Source"]
        source = Source(
            name=name,
            path=path if path is not None else f"hash-{name}",
            size=size,
            user=USER["id"],
            note=note
            if note is not None
            else {
                "loader": "PDFThumbnailReader",
                "tokens": 123,
                "summary": "内容摘录：这是摘要",
            },
        )
        with Session(self.engine) as session:
            session.add(source)
            session.commit()
            session.refresh(source)
            return source.id

    def seed_relation(self, source_id: str, target_id: str, kind="document") -> None:
        Index = self.index._resources["Index"]
        with Session(self.engine) as session:
            session.add(
                Index(
                    source_id=source_id,
                    target_id=target_id,
                    relation_type=kind,
                    user=USER["id"],
                )
            )
            session.commit()

    def count(self, model) -> int:
        with Session(self.engine) as session:
            return len(session.execute(select(model)).all())


@pytest.fixture()
def env(monkeypatch):
    # The sandbox this repository is developed in denies writes into *new*
    # subdirectories of the temporary directory (the same ACL that breaks
    # pytest's ``tmp_path``), so the database and the stored uploads are plain
    # files in the temporary root, named with a unique token.
    tmp_root = Path(tempfile.gettempdir())
    token = uuid.uuid4().hex[:10]
    db_path = tmp_root / f"ktem-api-files-{token}.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )

    # the index and both services must talk to the same throw-away database
    monkeypatch.setattr(file_index_module, "engine", test_engine)
    monkeypatch.setattr(files_service, "engine", test_engine)
    monkeypatch.setattr(settings_service, "engine", test_engine)

    vectorstore = FakeVectorStore()
    docstore = FakeDocumentStore()
    monkeypatch.setattr(
        file_index_module, "get_vectorstore", lambda name=None: vectorstore
    )
    monkeypatch.setattr(file_index_module, "get_docstore", lambda name=None: docstore)
    monkeypatch.setattr(file_index_module, "filestorage_path", tmp_root)
    # A scratch *directory* cannot be removed again in this sandbox (ACL on
    # newly created subdirectories), and the tests below never save an upload,
    # so point the service at a path that intentionally does not exist.
    monkeypatch.setattr(
        files_service.FileService,
        "upload_tempdir",
        staticmethod(lambda: tmp_root / f"{token}-uploads"),
    )

    index = file_index_module.FileIndex(
        app=None,
        id=1,
        name="test",
        config={"private": False, "max_file_size": 0, "max_number_of_files": 0},
    )
    index._setup_resources()
    # ``_setup_resources`` derives ``<root>/index_1``; the sandbox cannot write
    # into that new directory, and the service resolves stored uploads through
    # this resource, so point it at the writable root instead.
    index._resources["FileStoragePath"] = tmp_root
    for table in ("Source", "Index", "FileGroup"):
        index._resources[table].metadata.create_all(test_engine)
    Settings.__table__.create(test_engine, checkfirst=True)

    app = FakeApp(index)
    env = Env(
        engine=test_engine,
        index=index,
        vectorstore=vectorstore,
        docstore=docstore,
        app=app,
        tmp_root=tmp_root,
        token=token,
    )
    try:
        yield env
    finally:
        test_engine.dispose()
        db_path.unlink(missing_ok=True)
        for suffix in ("-journal", "-wal", "-shm"):
            (tmp_root / f"ktem-api-files-{token}.db{suffix}").unlink(missing_ok=True)
        for leftover in tmp_root.glob(f"{token}-*"):
            leftover.unlink(missing_ok=True)


# --------------------------------------------------------------------- auth
def test_anonymous_request_is_rejected(env):
    client = env.client(user=None)
    response = client.get("/files")
    assert response.status_code == 401, response.text


# --------------------------------------------------------------------- list
def test_file_list_columns_and_rows(env):
    first = env.seed_source("报告 2026.pdf", size=2048)
    env.seed_source("notes.txt", size=10)
    env.seed_relation(first, "doc-1")
    env.seed_relation(first, "doc-2")

    response = env.client().get("/files", params={"index_id": 1})
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["index_id"] == 1
    assert payload["columns"] == [
        "file_id",
        "name",
        "type",
        "size",
        "blocks",
        "loader",
        "profile",
        "date_created",
        "tokens",
    ]
    assert len(payload["rows"]) == 2

    row = next(item for item in payload["rows"] if item["file_id"] == first)
    assert row["name"] == "报告 2026.pdf"
    assert row["type"] == "pdf"
    assert row["size"] == "2KB"
    assert row["blocks"] == 2
    assert row["loader"] == "PDFThumbnailReader"
    assert row["tokens"] == 123
    assert row["profile"].startswith("这是摘要")


def test_file_list_filters_by_name(env):
    env.seed_source("alpha.pdf")
    env.seed_source("beta.txt")

    payload = env.client().get("/files", params={"query": "alp"}).json()
    assert [row["name"] for row in payload["rows"]] == ["alpha.pdf"]

    # LIKE metacharacters are literal, not wildcards
    payload = env.client().get("/files", params={"query": "%"}).json()
    assert payload["rows"] == []


def test_unknown_index_is_404(env):
    response = env.client().get("/files", params={"index_id": 99})
    assert response.status_code == 404


# ------------------------------------------------------------------- chunks
def test_chunks_of_an_unknown_file_are_404(env):
    response = env.client().get("/files/does-not-exist/chunks")
    assert response.status_code == 404
    assert "文件不存在" in response.json()["detail"]


def test_chunk_payload_and_type_filter(env):
    file_id = env.seed_source("mix.pdf")
    docs = {
        "d1": SimpleNamespace(text="正文", metadata={"type": "text", "page_label": 1}),
        "d2": SimpleNamespace(
            text="| a | b |", metadata={"type": "table", "page_label": 2}
        ),
        "d3": SimpleNamespace(text="图注", metadata={"type": "image", "page_label": 2}),
        "d4": SimpleNamespace(
            text="缩略图", metadata={"type": "thumbnail", "page_label": 3}
        ),
    }
    env.docstore.docs.update(docs)
    for target in docs:
        env.seed_relation(file_id, target)

    payload = env.client().get(f"/files/{file_id}/chunks").json()
    # The header goes through ``tr()``: when another test module has already
    # activated the Chinese catalog (session-scoped fixture) it is localized, so
    # assert against tr() instead of a hard-coded English string.
    from ktem.utils.i18n import tr

    assert payload["header"] == tr("{} chunks").format(4)
    assert payload["counts"] == {"text": 1, "table": 1, "image": 1, "thumbnail": 1}
    assert [chunk["index"] for chunk in payload["chunks"]] == [1, 2, 3, 4]
    assert [chunk["page"] for chunk in payload["chunks"]] == [1, 2, 2, 3]
    assert payload["chunks"][1]["type"] == "table"
    assert payload["chunks"][1]["html"] == ""

    tables = env.client().get(
        f"/files/{file_id}/chunks", params={"type": "table"}
    ).json()
    assert tables["header"] == tr("{} chunks").format(1)
    assert [chunk["text"] for chunk in tables["chunks"]] == ["| a | b |"]
    assert tables["counts"]["text"] == 1  # counts describe the whole file


# ------------------------------------------------------------------- delete
def test_delete_removes_rows_embeddings_and_upload(env):
    stored_name = env.write_stored("gone.pdf", b"payload")
    file_id = env.seed_source("gone.pdf", path=stored_name)
    env.seed_relation(file_id, "vec-1", kind="vector")
    env.seed_relation(file_id, "doc-1")
    stored = env.index._resources["FileStoragePath"] / stored_name

    response = env.client().delete(f"/files/{file_id}")
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True

    assert env.count(env.index._resources["Source"]) == 0
    assert env.count(env.index._resources["Index"]) == 0
    assert env.vectorstore.deleted == ["vec-1"]
    assert env.docstore.deleted == ["doc-1"]
    assert not stored.exists()


def test_delete_of_unknown_file_is_404(env):
    response = env.client().delete("/files/nope")
    assert response.status_code == 404


# ----------------------------------------------------------------- download
def test_download_serves_the_stored_bytes(env):
    stored_name = env.write_stored("manual.pdf", b"%PDF-1.4 test")
    file_id = env.seed_source("manual.pdf", path=stored_name)

    response = env.client().get(f"/files/{file_id}/download")
    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 test"
    assert "manual.pdf" in response.headers.get("content-disposition", "")


def test_download_of_a_missing_copy_is_404(env):
    file_id = env.seed_source("missing.pdf", path=env.stored_name("not-there.pdf"))
    response = env.client().get(f"/files/{file_id}/download")
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]


# ------------------------------------------------------------------- groups
def test_group_crud(env):
    client = env.client()

    created = client.post("/groups", json={"name": "第一组", "files": ["f1"]})
    assert created.status_code == 200, created.text
    group = created.json()["item"]
    assert group["name"] == "第一组"
    assert group["files"] == ["f1"]
    assert group["date_created"]

    listed = client.get("/groups").json()["items"]
    assert [item["id"] for item in listed] == [group["id"]]

    updated = client.patch(
        f"/groups/{group['id']}", json={"name": "第二组", "files": ["f1", "f2"]}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["item"]["name"] == "第二组"
    assert updated.json()["item"]["files"] == ["f1", "f2"]

    deleted = client.delete(f"/groups/{group['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    assert client.get("/groups").json()["items"] == []


def test_group_name_must_be_unique_and_non_empty(env):
    client = env.client()
    assert client.post("/groups", json={"name": "G", "files": []}).status_code == 200

    duplicate = client.post("/groups", json={"name": "G", "files": []})
    assert duplicate.status_code == 400
    assert "已存在" in duplicate.json()["detail"]

    empty = client.post("/groups", json={"name": "   ", "files": []})
    assert empty.status_code == 400
    assert "不能为空" in empty.json()["detail"]


def test_group_unknown_ids_are_404(env):
    client = env.client()
    assert client.patch("/groups/nope", json={"name": "X"}).status_code == 404
    assert client.delete("/groups/nope").status_code == 404


# ------------------------------------------------------------------- upload
def test_upload_without_content_is_400(env):
    response = env.client().post("/files/upload", data={})
    assert response.status_code == 400
    assert "没有选择文件" in response.json()["detail"]


def test_upload_invalid_url_streams_an_error_frame(env):
    response = env.client().post(
        "/files/upload", data={"urls": "not-a-url", "index_id": "1"}
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: error" in body
    assert "无效的网址" in body
    assert "event: done" not in body


def test_reindex_of_unknown_file_is_404(env):
    response = env.client().post("/files/nope/reindex")
    assert response.status_code == 404
    assert "文件不存在" in response.json()["detail"]


def test_reindex_of_a_url_source_is_400(env):
    file_id = env.seed_source("https://example.com/paper", path="")
    response = env.client().post(f"/files/{file_id}/reindex")
    assert response.status_code == 400
    assert "不支持重建索引" in response.json()["detail"]
