"""Read-only resources and bundled help documents."""

from __future__ import annotations

import uuid


def test_resources_list_indices_and_model_pools(logged_in):
    response = logged_in.get("/api/v1/resources")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["indices"], "the fixture index should be listed"
    index = payload["indices"][0]
    assert set(index) == {"id", "name", "private", "file_count"}

    for pool in ("llms",):
        assert isinstance(payload[pool], list)
        for row in payload[pool]:
            assert set(row) == {"name", "vendor", "model", "default"}
            assert isinstance(row["default"], bool)

    # Embeddings and rerankers additionally say which one the index runs on.
    for pool in ("embeddings", "rerankings"):
        assert isinstance(payload[pool], list)
        for row in payload[pool]:
            assert set(row) == {"name", "vendor", "model", "default", "in_use"}
            assert isinstance(row["default"], bool)
            assert isinstance(row["in_use"], bool)

    # The specs carry API keys; the endpoint must only expose the vendor class.
    assert "api_key" not in response.text
    assert "spec" not in response.text


def test_embeddings_mark_the_model_the_index_uses(logged_in):
    """The embedding pool is read-only here, so it marks what is really in use.

    The fixture index stores ``"embedding": "default"``; that alias has to be
    resolved to the pool default before the page can badge a row (MODIFICATIONS
    §5.35).
    """
    payload = logged_in.get("/api/v1/resources").json()
    embeddings = payload["embeddings"]
    assert embeddings, "the deployment has an embedding model"

    used = [row["name"] for row in embeddings if row["in_use"]]
    defaults = [row["name"] for row in embeddings if row["default"]]
    assert len(used) == 1, "the single fixture index runs on one embedding model"
    assert used == defaults, "the alias `default` resolves to the pool default"

    # Nothing else claims to be in use.
    assert all(name in {row["name"] for row in embeddings} for name in used)

    rerankers = payload["rerankings"]
    assert rerankers, "the deployment has a reranker"
    reranker_used = [row["name"] for row in rerankers if row["in_use"]]
    assert reranker_used == [row["name"] for row in rerankers if row["default"]]


def test_help_serves_the_bundled_documents(logged_in):
    response = logged_in.get("/api/v1/help")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["app"]["name"]
    assert payload["app"]["version"]
    assert payload["about_md"].strip(), "docs/about.<lang>.md should be bundled"
    assert payload["usage_md"].strip(), "docs/usage.<lang>.md should be bundled"


def test_resources_and_help_require_a_session(client):
    assert client.get("/api/v1/resources").status_code == 401
    assert client.get("/api/v1/help").status_code == 401
    assert (
        client.put("/api/v1/resources/llm", json={"name": "deepseek"}).status_code
        == 401
    )


def _ensure_two_models(client) -> tuple[set[str], list[str]]:
    """Make the pool testable: a fresh, unconfigured install has no model at all."""
    meta = client.get("/api/v1/meta").json()
    pool = {item["value"] for item in meta["models"]["choices"]} - {""}
    created: list[str] = []
    while len(pool) < 2:
        name = f"test-llm-{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/vendors/llms",
            json={
                "name": name,
                "vendor": "ChatOpenAI",
                "params": {"api_key": "test-key", "model": "gpt-4o-mini"},
            },
        )
        assert response.status_code == 201, response.text
        created.append(name)
        pool.add(name)
    return pool, created


def test_current_llm_follows_the_account_choice(logged_in):
    """The model the chat runs on is a per-user choice, not the global default.

    ``/resources/llm`` writes it, ``/meta`` reports it, and an empty name clears the
    override so the pool default applies again (MODIFICATIONS §5.33).
    """
    meta = logged_in.get("/api/v1/meta").json()
    reasoning = meta["reasoning"]["default"]
    key = f"reasoning.options.{reasoning}.llm"
    settings = logged_in.get("/api/v1/settings").json()["values"]
    original_setting = settings.get(key, "")

    pool, created = _ensure_two_models(logged_in)
    fallback = logged_in.get("/api/v1/meta").json()["models"]["default"]
    other = sorted(pool - {fallback})[0]

    try:
        switched = logged_in.put("/api/v1/resources/llm", json={"name": other})
        assert switched.status_code == 200, switched.text
        assert switched.json()["name"] == other
        assert logged_in.get("/api/v1/meta").json()["models"]["default"] == other
        assert logged_in.get("/api/v1/settings").json()["values"][key] == other

        # An unknown model is rejected and leaves the choice untouched.
        bad = logged_in.put("/api/v1/resources/llm", json={"name": "no-such-model"})
        assert bad.status_code == 400
        assert logged_in.get("/api/v1/meta").json()["models"]["default"] == other

        # Clearing the override falls back to the pool default.
        cleared = logged_in.put("/api/v1/resources/llm", json={"name": ""})
        assert cleared.status_code == 200, cleared.text
        assert logged_in.get("/api/v1/meta").json()["models"]["default"] in pool
    finally:
        # The API suite shares the real app database: put the account setting back
        # first, then remove the models this test created.
        logged_in.put("/api/v1/settings", json={"values": {key: original_setting}})
        for name in created:
            logged_in.delete(f"/api/v1/vendors/llms/{name}")
