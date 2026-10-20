"""Switching the embedding or the reranker model (MODIFICATIONS §5.36).

An embedding switch changes the vector space, so the index has to be rebuilt:
the stores are dropped and every stored upload re-embedded. These tests pin that
flow with fakes (no model call, no real store), and the API contract around it.
"""

from __future__ import annotations

import threading
import time
import types
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kotaemon.base import Document

import ktem.embeddings.manager as embeddings_module
from ktem.services import reindex as reindex_module
from ktem.services.reindex import ReindexJob, rebuild_all


# --------------------------------------------------------------------------- #
# fakes: no database, no LanceDB, no embedding call
# --------------------------------------------------------------------------- #
class FakePipeline:
    def __init__(self, statuses=("success",)):
        self.statuses = list(statuses)
        self.calls: list[tuple[list, bool, dict]] = []

    def stream(self, paths, reindex, **kwargs):
        self.calls.append((list(paths), reindex, dict(kwargs)))
        for status in self.statuses:
            yield Document(
                channel="index",
                content={"file_name": "文件.pdf", "status": status},
            )


class FakeIndex:
    def __init__(self, index_id=1, statuses=("success",)):
        self.id = index_id
        self.name = f"索引{index_id}"
        self.config = {"embedding": "default"}
        self._fs_path = ""
        self._resources = {"Index": object()}
        self.pipelines: list[FakePipeline] = []
        self._statuses = statuses

    def get_indexing_pipeline(self, settings, user_id):
        pipeline = FakePipeline(self._statuses)
        pipeline.user_id = user_id
        self.pipelines.append(pipeline)
        return pipeline


class FakeIndexManager:
    def __init__(self, indices):
        self.indices = list(indices)
        self.updates: list[tuple[int, str, dict]] = []

    def update_index(self, index_id, name, config):
        self.updates.append((index_id, name, dict(config)))
        for index in self.indices:
            if index.id == index_id:
                index.config = dict(config)


class FakeEmbeddingManager:
    def __init__(self, names=("old", "new")):
        self.names = list(names)
        self.updates: list[tuple] = []
        self._default = self.names[0] if self.names else ""

    def info(self):
        return {
            name: {
                "name": name,
                "spec": {"__type__": "kotaemon.embeddings.OpenAIEmbeddings"},
                "default": name == self._default,
            }
            for name in self.names
        }

    def options(self):
        return {name: object() for name in self.names}

    def update(self, name, spec, default, new_name=""):
        self.updates.append((name, spec, default))
        if default:
            self._default = name


class FakeApp:
    def __init__(self, indices):
        self.index_manager = FakeIndexManager(indices)
        self.default_settings = types.SimpleNamespace(flatten=lambda: {})


@pytest.fixture()
def fake_environment(monkeypatch, tmp_path):
    """Two indices with one stored file each, and every store call faked."""
    stored = {}
    dropped: list[int] = []

    def fake_sources(index):
        path = tmp_path / f"source-{index.id}.pdf"
        path.write_bytes(b"%PDF-1.4 fake")
        return [
            {
                "id": f"file-{index.id}",
                "name": f"制度{index.id}.pdf",
                "path": path,
                "user": 7,
            }
        ]

    manager = FakeEmbeddingManager()
    monkeypatch.setattr(reindex_module, "stored_sources", fake_sources)
    monkeypatch.setattr(
        reindex_module, "drop_stores", lambda index: dropped.append(index.id)
    )
    monkeypatch.setattr(embeddings_module, "embedding_models_manager", manager)
    indices = [FakeIndex(1), FakeIndex(2)]
    app = FakeApp(indices)
    return types.SimpleNamespace(
        app=app, indices=indices, dropped=dropped, manager=manager, stored=stored
    )


# --------------------------------------------------------------------------- #
# rebuilding
# --------------------------------------------------------------------------- #
def test_switch_updates_configs_drops_stores_and_reindexes_every_file(
    fake_environment,
):
    env = fake_environment
    reports: list[dict] = []

    result = rebuild_all(env.app, "new", lambda **changes: reports.append(changes))

    assert env.manager.updates == [
        ("new", {"__type__": "kotaemon.embeddings.OpenAIEmbeddings"}, True)
    ], "the pool default moves to the chosen model"
    assert [index.config["embedding"] for index in env.indices] == ["new", "new"]
    assert env.dropped == [1, 2], "vectors of the old model cannot be reused"
    for index in env.indices:
        assert len(index.pipelines) == 1
        pipeline = index.pipelines[0]
        assert pipeline.calls[0][1] is True, "a switch always re-parses the files"
        assert (
            pipeline.calls[0][2]["keep_on_failure"] is True
        ), "a failed reindex must keep the row and the upload it created"
        assert pipeline.user_id == 7, "each file is re-indexed for its owner"
    assert result == {"total": 2, "done": 2, "failed": 0, "skipped": 0}
    assert reports[0]["state"] == "running"
    assert reports[0]["total"] == 2
    assert reports[-1]["done"] == 2


def test_a_file_that_fails_does_not_stop_the_rebuild(fake_environment):
    env = fake_environment
    env.indices[0]._statuses = ("failed",)

    result = rebuild_all(env.app, "new", lambda **changes: None)

    assert result == {"total": 2, "done": 1, "failed": 1, "skipped": 0}


def test_a_stored_file_that_is_gone_is_counted_as_failed(fake_environment, tmp_path):
    env = fake_environment
    original = reindex_module.stored_sources

    def half_missing(index):
        sources = original(index)
        if index.id == 1:
            sources[0] = dict(sources[0], path=tmp_path / "缺.pdf")
        return sources

    reindex_module.stored_sources = half_missing  # type: ignore[assignment]
    try:
        result = rebuild_all(env.app, "new", lambda **changes: None)
    finally:
        reindex_module.stored_sources = original  # type: ignore[assignment]

    assert result == {"total": 2, "done": 1, "failed": 1, "skipped": 0}


def test_a_failed_file_keeps_its_uploaded_bytes(fake_environment):
    """The pipeline deletes the old copy before parsing; a failure must not lose it."""
    env = fake_environment
    seen: list = []

    class DeletingPipeline(FakePipeline):
        def stream(self, paths, reindex, **kwargs):
            seen[0].unlink()  # the pipeline's reindex path deletes the old copy
            raise RuntimeError("解析失败")
            yield  # pragma: no cover - the generator never yields

    env.indices[0].get_indexing_pipeline = lambda settings, user_id: DeletingPipeline()
    original = reindex_module.stored_sources

    def capture(index):
        sources = original(index)
        if index.id == 1:
            seen.append(Path(sources[0]["path"]))
        return sources

    reindex_module.stored_sources = capture  # type: ignore[assignment]
    try:
        result = rebuild_all(env.app, "new", lambda **changes: None)
    finally:
        reindex_module.stored_sources = original  # type: ignore[assignment]

    assert result == {"total": 2, "done": 1, "failed": 1, "skipped": 0}
    assert seen[0].exists(), "the upload is restored from the scratch copy"


# --------------------------------------------------------------------------- #
# the background job
# --------------------------------------------------------------------------- #
def _wait_for(job, wanted, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = job.snapshot()
        if state["state"] == wanted:
            return state
        time.sleep(0.01)
    raise AssertionError(f"job never reached {wanted}: {job.snapshot()}")


def test_job_reports_progress_and_finishes():
    def rebuild(app, name, report):
        report(state="running", total=2, done=0)
        report(done=2)
        return {"total": 2, "done": 2, "failed": 0}

    job = ReindexJob(rebuild=rebuild)
    assert job.snapshot()["state"] == "idle"

    job.start(None, "new")
    state = _wait_for(job, "done")
    assert state["embedding"] == "new"
    assert (state["done"], state["total"], state["failed"]) == (2, 2, 0)
    assert state["message"]


def test_job_reports_a_failure():
    def rebuild(app, name, report):
        raise ValueError("连接失败")

    job = ReindexJob(rebuild=rebuild)
    job.start(None, "new")
    state = _wait_for(job, "error")
    assert "连接失败" in state["message"]


def test_only_one_rebuild_runs_at_a_time():
    started = threading.Event()
    release = threading.Event()

    def rebuild(app, name, report):
        started.set()
        release.wait(5)
        return {"total": 0, "done": 0, "failed": 0}

    job = ReindexJob(rebuild=rebuild)
    job.start(None, "new")
    assert started.wait(2)
    try:
        with pytest.raises(RuntimeError):
            job.start(None, "other")
    finally:
        release.set()
    _wait_for(job, "done")


# --------------------------------------------------------------------------- #
# API contract
# --------------------------------------------------------------------------- #
def _create_temp_embedding(client) -> str:
    name = f"test-switch-emb-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/vendors/embeddings",
        json={
            "name": name,
            "vendor": "OpenAIEmbeddings",
            "params": {"api_key": "sk-test", "model": "text-embedding-3-large"},
        },
    )
    assert response.status_code == 201, response.text
    return name


def test_switch_endpoints_require_an_admin(logged_in):
    created = logged_in.post(
        "/api/v1/users",
        json={
            "username": f"switch_user_{uuid.uuid4().hex[:6]}",
            "password": "Abcd1234!",
            "admin": False,
        },
    )
    assert created.status_code == 201, created.text
    user = created.json()
    try:
        other = TestClient(logged_in.app)
        login = other.post(
            "/api/v1/auth/login",
            json={"username": user["username"], "password": "Abcd1234!"},
        )
        assert login.status_code == 200, login.text
        for path in ("/api/v1/resources/embedding", "/api/v1/resources/reranking"):
            response = other.put(path, json={"name": "x"})
            assert response.status_code == 403, response.text
    finally:
        assert logged_in.delete(f"/api/v1/users/{user['id']}").status_code == 204


def test_switches_are_not_writable_anonymously(client):
    assert (
        client.put("/api/v1/resources/embedding", json={"name": "x"}).status_code == 401
    )
    assert (
        client.put("/api/v1/resources/reranking", json={"name": "x"}).status_code == 401
    )
    assert client.get("/api/v1/resources/embedding/job").status_code == 401


def test_an_unknown_model_is_rejected(logged_in):
    for path in ("/api/v1/resources/embedding", "/api/v1/resources/reranking"):
        response = logged_in.put(path, json={"name": "no-such-model"})
        assert response.status_code == 400, response.text


def test_switching_to_the_model_already_in_use_does_nothing(logged_in, monkeypatch):
    rows = logged_in.get("/api/v1/resources").json()

    class ExplodingJob:
        calls = 0

        def snapshot(self):
            return {
                "state": "idle",
                "embedding": "",
                "total": 0,
                "done": 0,
                "failed": 0,
                "message": "",
            }

        def start(self, app, name):
            ExplodingJob.calls += 1
            raise AssertionError("a no-op switch must not start a rebuild")

    from ktem.api import resources as resources_module

    monkeypatch.setattr(resources_module, "reindex_job", ExplodingJob())
    current = next(row["name"] for row in rows["embeddings"] if row["in_use"])

    response = logged_in.put("/api/v1/resources/embedding", json={"name": current})

    assert response.status_code == 200, response.text
    assert response.json()["started"] is False
    assert ExplodingJob.calls == 0


def test_a_failed_rebuild_can_be_retried_for_the_same_model(logged_in, monkeypatch):
    """The model is "in use" after a failed rebuild, so a retry must still start."""
    from ktem.api import resources as resources_module

    class RetryJob:
        started: list[str] = []

        def snapshot(self):
            return {
                "state": "error",
                "embedding": "dashscope",
                "total": 2,
                "done": 0,
                "failed": 2,
                "message": "重建失败：连接中断",
            }

        def start(self, app, name):
            RetryJob.started.append(name)
            return {**self.snapshot(), "state": "running", "embedding": name}

    monkeypatch.setattr(resources_module, "reindex_job", RetryJob())
    current = next(
        row["name"]
        for row in logged_in.get("/api/v1/resources").json()["embeddings"]
        if row["in_use"]
    )

    response = logged_in.put("/api/v1/resources/embedding", json={"name": current})

    assert response.status_code == 200, response.text
    assert response.json()["started"] is True
    assert RetryJob.started == [current]


def test_switching_the_embedding_starts_a_rebuild(logged_in, monkeypatch):
    from ktem.api import resources as resources_module

    releases = threading.Event()

    def rebuild(app, name, report):
        report(state="running", total=1, done=0)
        releases.wait(5)
        return {"total": 1, "done": 1, "failed": 0}

    monkeypatch.setattr(resources_module, "reindex_job", ReindexJob(rebuild=rebuild))
    name = _create_temp_embedding(logged_in)
    try:
        response = logged_in.put("/api/v1/resources/embedding", json={"name": name})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["started"] is True
        started = payload["job"]
        assert started["state"] == "running"
        assert started["embedding"] == name

        # A second switch while the rebuild runs is refused.
        again = logged_in.put("/api/v1/resources/embedding", json={"name": name})
        assert again.status_code == 409, again.text

        polled = logged_in.get("/api/v1/resources/embedding/job").json()["job"]
        assert polled["state"] == "running"
        assert polled["total"] == 1
    finally:
        releases.set()
        assert logged_in.delete(f"/api/v1/vendors/embeddings/{name}").status_code == 204


def test_a_url_source_is_skipped_and_the_switch_then_becomes_a_noop(
    logged_in, monkeypatch, fake_environment, tmp_path
):
    """A web link cannot be re-parsed with the new model: skip it, don't fail it.

    Counting the link as failed kept the finished job dirty, so switching to the
    same model again started another full rebuild every time; ``skipped`` is
    informational and must not affect the no-op decision.
    """
    from ktem.api import resources as resources_module

    uploaded = tmp_path / "制度.pdf"
    uploaded.write_bytes(b"%PDF-1.4 fake")
    sources = [
        {
            "id": "url-1",
            "name": "https://example.com/制度",
            "path": tmp_path / "url",
            "user": 7,
        },
        {"id": "file-1", "name": "制度.pdf", "path": uploaded, "user": 7},
    ]
    monkeypatch.setattr(reindex_module, "stored_sources", lambda index: sources)

    single = FakeApp([FakeIndex(1)])
    job = ReindexJob(
        rebuild=lambda app, name, report: rebuild_all(single, name, report)
    )
    monkeypatch.setattr(resources_module, "reindex_job", job)

    try:
        response = logged_in.put("/api/v1/resources/embedding", json={"name": "new"})
        assert response.status_code == 200, response.text
        assert response.json()["started"] is True

        state = _wait_for(job, "done")
        assert state["failed"] == 0, state
        assert state["skipped"] == 1, state
        assert state["done"] == 1, state
        assert state["total"] == 2, state
        assert state["message"]

        again = logged_in.put("/api/v1/resources/embedding", json={"name": "new"})
        assert again.status_code == 200, again.text
        assert again.json()["started"] is False
    finally:
        deadline = time.time() + 5
        while job.snapshot()["state"] == "running" and time.time() < deadline:
            time.sleep(0.01)


def test_switching_the_reranker_moves_the_default(logged_in):
    before = [
        row["name"]
        for row in logged_in.get("/api/v1/resources").json()["rerankings"]
        if row["default"]
    ]
    name = f"test-switch-rerank-{uuid.uuid4().hex[:8]}"
    created = logged_in.post(
        "/api/v1/vendors/rerankings",
        json={
            "name": name,
            "vendor": "CohereReranking",
            "params": {"cohere_api_key": "sk-test"},
            "default": False,
        },
    )
    assert created.status_code == 201, created.text
    try:
        response = logged_in.put("/api/v1/resources/reranking", json={"name": name})
        assert response.status_code == 200, response.text
        assert response.json()["name"] == name

        rows = logged_in.get("/api/v1/resources").json()["rerankings"]
        used = [row["name"] for row in rows if row["in_use"]]
        assert used == [name], "the reranker in use is the pool default"
    finally:
        for original in before:
            logged_in.put("/api/v1/resources/reranking", json={"name": original})
        logged_in.delete(f"/api/v1/vendors/rerankings/{name}")
