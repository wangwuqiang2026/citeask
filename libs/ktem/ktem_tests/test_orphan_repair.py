"""Tests for the orphan-file repair (``ktem.index.file.repair``).

An orphan is a source row that cannot be retrieved: either it has no chunks at all,
or — the shape a failed run actually leaves behind — it has documents in the
document store and no vectors, because indexing writes documents first and vectors
last. That is what MODIFICATIONS §2.7 (``.docx``) and §2.9 (``.xls``) looked like
from the outside: the file is listed, questions about it answer "No evidence
found". The repair re-parses such a file from its stored copy on startup, so fixing
a reader (or a batch size) heals the existing corpus.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import JSON, Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool

from ktem.index.file import repair as repair_module

Base = declarative_base()


class _Source(Base):
    """Stand-in for the table ``FileIndex`` generates per index."""

    __tablename__ = "index__1__source"

    id = Column(String, primary_key=True)
    name = Column(String)
    path = Column(String)
    user = Column(String, default="")
    note = Column(JSON, default=dict)


class _Index(Base):
    """Stand-in for the source <-> chunk relation table."""

    __tablename__ = "index__1__index"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String)
    target_id = Column(String)
    relation_type = Column(String)
    user = Column(String, default="")


class _StubPipeline:
    """Records how the repair called the reader, then replays fixed events."""

    def __init__(self, events, calls, on_stream=None):
        self._events = events
        self._calls = calls
        self._on_stream = on_stream

    def stream(self, file_path, reindex=False, keep_on_failure=False):
        path = Path(file_path)
        self._calls.append(
            {
                "path": path,
                "existed": path.exists(),
                "content": path.read_bytes() if path.exists() else b"",
                "reindex": reindex,
                "keep_on_failure": keep_on_failure,
            }
        )
        if self._on_stream is not None:
            self._on_stream()
        yield from self._events


def _success():
    return [SimpleNamespace(channel="index", content={"status": "success"})]


def _failure(message):
    return [
        SimpleNamespace(
            channel="index",
            content={"status": "failed", "message": message},
        )
    ]


@pytest.fixture
def workdir():
    """Scratch directory that does not depend on pytest's tmp_path plugin."""
    # Path.mkdir (not tempfile.mkdtemp): the latter creates a 0o700 directory, which
    # is not writable inside the Windows sandbox used for local runs.
    path = Path(tempfile.gettempdir()) / f"orphan-repair-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def index(workdir, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(repair_module, "engine", engine)

    files = workdir / "files"
    files.mkdir()
    return SimpleNamespace(
        id=1,
        name="File Collection",
        _resources={
            "Source": _Source,
            "Index": _Index,
            "FileStoragePath": files,
        },
        files_dir=files,
    )


def add_source(index, name, *, chunks=0, vectors=None, note=None, store=True):
    """Insert a source row, its relation rows and its stored copy.

    ``chunks`` document relations are written (the text chunks) and ``vectors``
    vector relations (what retrieval actually uses); ``vectors`` defaults to
    ``chunks``, i.e. a completely indexed file.
    """
    source_id = f"source-{name}"
    stored_name = f"hash-{name}"
    n_vectors = chunks if vectors is None else vectors
    with repair_module.Session(repair_module.engine) as session:
        session.add(
            _Source(
                id=source_id,
                name=name,
                path=stored_name,
                user="user-1",
                note=note or {},
            )
        )
        for i in range(chunks):
            session.add(
                _Index(
                    source_id=source_id,
                    target_id=f"{name}-doc-{i}",
                    relation_type="document",
                )
            )
        for i in range(n_vectors):
            session.add(
                _Index(
                    source_id=source_id,
                    target_id=f"{name}-vec-{i}",
                    relation_type="vector",
                )
            )
        session.commit()
    if store:
        (index.files_dir / stored_name).write_bytes(b"stored-upload")
    return source_id


def factory(events, calls, on_stream=None):
    def _build(_index, _settings, _user):
        return _StubPipeline(events, calls, on_stream=on_stream)

    return _build


def test_find_orphans_ignores_files_that_have_vectors(index):
    add_source(index, "indexed.xlsx", chunks=3)
    add_source(index, "orphan.xls", chunks=0)

    assert [o["name"] for o in repair_module.find_orphans(index)] == ["orphan.xls"]


def test_a_half_indexed_file_is_an_orphan(index):
    """Documents without vectors is the state a failed embedding run leaves.

    Indexing writes the document store first and the vectors afterwards, so a
    failure while embedding leaves a file with 10k documents and no vectors: it is
    listed and looks indexed, but retrieval (which uses the vectors) never returns
    it. Counting documents would consider such a file healthy and skip the repair —
    that is exactly how the 9.6 MB spreadsheet stayed unusable.
    """
    add_source(index, "half.xls", chunks=10237, vectors=0)

    assert [o["name"] for o in repair_module.find_orphans(index)] == ["half.xls"]


def test_repair_parses_the_stored_copy_under_its_original_name(index, workdir):
    add_source(index, "招考简章.xls")
    calls = []

    outcome = repair_module.repair_orphans(
        index,
        {},
        restore_dir=workdir / "work",
        pipeline_factory=factory(_success(), calls),
    )

    assert outcome["repaired"] == ["招考简章.xls"]
    assert len(calls) == 1
    # the store keeps a bare hash: the reader is chosen by the extension, so the
    # repair has to hand the pipeline a name that still ends in .xls
    assert calls[0]["path"].name == "招考简章.xls"
    assert calls[0]["existed"] is True
    assert calls[0]["content"] == b"stored-upload"
    assert calls[0]["reindex"] is True
    # the retry must not delete the row when it fails as well
    assert calls[0]["keep_on_failure"] is True


def test_a_failed_repair_keeps_the_upload_and_records_the_reason(index, workdir):
    add_source(index, "orphan.xls")

    outcome = repair_module.repair_orphans(
        index,
        {},
        restore_dir=workdir / "work",
        pipeline_factory=factory(_failure("Missing optional dependency 'xlrd'"), []),
    )

    assert outcome["failed"] == ["orphan.xls"]
    orphans = repair_module.find_orphans(index)
    assert [o["name"] for o in orphans] == ["orphan.xls"], "the upload was deleted"
    assert "xlrd" in orphans[0]["note"]["error"]
    assert orphans[0]["note"]["repair_attempts"] == 1


def test_a_failed_retry_is_recorded_on_the_row_the_retry_recreated(index, workdir):
    """``reindex=True`` deletes the row and stores it again, so its id changes.

    Recording the failure against the id collected before the retry silently lost
    the attempt counter, and the file was re-parsed at every start — forever.
    """
    old_id = add_source(index, "orphan.xls")

    def recreate_row():
        with repair_module.Session(repair_module.engine) as session:
            session.query(_Source).delete()
            session.add(
                _Source(
                    id="source-recreated",
                    name="orphan.xls",
                    path="hash-orphan.xls",
                    user="user-1",
                    note={},
                )
            )
            session.commit()

    outcome = repair_module.repair_orphans(
        index,
        {},
        restore_dir=workdir / "work",
        pipeline_factory=factory(_failure("Missing optional dependency 'xlrd'"), [], recreate_row),
    )

    assert outcome["failed"] == ["orphan.xls"]
    orphans = repair_module.find_orphans(index)
    assert len(orphans) == 1
    assert orphans[0]["id"] != old_id
    assert orphans[0]["note"]["repair_attempts"] == 1


def test_a_file_without_a_stored_copy_fails_instead_of_crashing(index, workdir):
    add_source(index, "gone.pdf", store=False)
    calls = []

    outcome = repair_module.repair_orphans(
        index,
        {},
        restore_dir=workdir / "work",
        pipeline_factory=factory(_success(), calls),
    )

    assert outcome["failed"] == ["gone.pdf"]
    assert calls == []
    orphans = repair_module.find_orphans(index)
    assert orphans[0]["note"]["error"] == "stored file is missing"


def test_repair_stops_after_max_attempts(index, workdir):
    add_source(
        index, "stubborn.xls", note={"repair_attempts": repair_module.MAX_ATTEMPTS}
    )
    calls = []

    outcome = repair_module.repair_orphans(
        index,
        {},
        restore_dir=workdir / "work",
        pipeline_factory=factory(_success(), calls),
    )

    assert outcome["skipped"] == ["stubborn.xls"]
    assert calls == [], "a file at the attempt cap must not be re-parsed again"


def test_a_source_owner_is_used_for_its_own_repair(index, workdir):
    add_source(index, "owner.xls")
    seen_users = []

    def _build(_index, _settings, user):
        seen_users.append(user)
        return _StubPipeline(_success(), [])

    repair_module.repair_orphans(
        index, {}, restore_dir=workdir / "work", pipeline_factory=_build
    )

    assert seen_users == ["user-1"]


def test_loader_column_shows_the_failure_reason():
    from ktem.index.file.ui import MAX_ERROR_LENGTH, describe_loader

    assert describe_loader({"loader": "PandasExcelReader"}) == "PandasExcelReader"
    assert describe_loader({}) == "-"
    assert describe_loader(None) == "-"

    text = describe_loader({"error": "Missing optional dependency 'xlrd'"})
    assert text.startswith("\u26a0") and "xlrd" in text

    truncated = describe_loader({"error": "x" * 200})
    assert len(truncated) <= MAX_ERROR_LENGTH + 2
    assert truncated.endswith("...")


def test_a_failed_upload_leaves_no_phantom_file():
    """A parse that fails must not leave a source row behind.

    The row used to survive (MODIFICATIONS §2.9): the file stayed in the list as if
    it were indexed, questions about it answered "No evidence found", and uploading
    it again came back as "already indexed" — the user had no way out.
    """
    from ktem.index.file.pipelines import IndexPipeline

    class _FakeSelf:
        def __init__(self):
            self.deleted = []
            self.dropped = []

        def delete_file(self, file_id):
            self.deleted.append(file_id)

        def delete_chunks(self, file_id):
            self.dropped.append(file_id)

    def attempt(*, created_here, keep_on_failure, reused_row=False):
        fake = _FakeSelf()
        IndexPipeline._handle_failed_indexing(
            fake,
            file_id="source-1",
            file_path=Path("orphan.xls"),
            file_name="orphan.xls",
            error=RuntimeError("Missing optional dependency 'xlrd'"),
            created_here=created_here,
            reused_row=reused_row,
            keep_on_failure=keep_on_failure,
        )
        return fake.deleted, fake.dropped

    # an upload that failed: the row goes, so re-uploading works
    assert attempt(created_here=True, keep_on_failure=False) == (["source-1"], [])
    # a row that existed before this attempt belongs to an earlier upload
    assert attempt(created_here=False, keep_on_failure=False) == ([], [])
    # the startup repair retries an existing row: keep it, but drop the partial
    # chunks so the next retry does not write 10k documents on top of 10k
    assert attempt(created_here=True, keep_on_failure=True) == ([], ["source-1"])
    # a reindex reuses the row (§5.37): the user's upload must survive the failure
    assert attempt(created_here=False, keep_on_failure=False, reused_row=True) == (
        [],
        ["source-1"],
    )
