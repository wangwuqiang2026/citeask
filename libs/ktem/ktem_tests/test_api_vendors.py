"""Vendor catalog and CRUD, including the default-model bookkeeping."""

from __future__ import annotations

from fastapi.testclient import TestClient

TEST_LLM = "test_api_llm"
TEST_EMBEDDING = "test_api_embedding"
TEST_MCP = "test_api_mcp"


def _delete(client, kind: str, name: str) -> None:
    client.delete(f"/api/v1/vendors/{kind}/{name}")


def _default_names(client) -> list[str]:
    rows = client.get("/api/v1/vendors/llms").json()["items"]
    return [row["name"] for row in rows if row["default"]]


def test_catalog_lists_vendors_with_form_metadata(logged_in):
    catalog = logged_in.get("/api/v1/vendors").json()

    llms = {vendor["name"]: vendor for vendor in catalog["llms"]}
    assert "ChatOpenAI" in llms
    params = {param["name"]: param for param in llms["ChatOpenAI"]["params"]}
    assert params["api_key"]["required"] is True
    assert params["api_key"]["secret"] is True
    assert params["api_key"]["type"] == "str"

    assert catalog["embeddings"], "embedding vendors should be listed"
    assert catalog["rerankings"], "reranking vendors should be listed"
    assert catalog["mcp"] == []


def test_llm_crud_round_trip(logged_in):
    before = _default_names(logged_in)
    try:
        created = logged_in.post(
            "/api/v1/vendors/llms",
            json={
                "name": TEST_LLM,
                "vendor": "ChatOpenAI",
                "params": {"api_key": "sk-test", "model": "gpt-4o-mini"},
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["vendor"] == "ChatOpenAI"

        listed = logged_in.get("/api/v1/vendors/llms").json()["items"]
        assert any(row["name"] == TEST_LLM for row in listed)

        entry = logged_in.get(f"/api/v1/vendors/llms/{TEST_LLM}").json()
        assert entry["spec"]["__type__"].endswith("ChatOpenAI")
        assert entry["spec"]["api_key"] == "sk-test"

        duplicate = logged_in.post(
            "/api/v1/vendors/llms",
            json={"name": TEST_LLM, "vendor": "ChatOpenAI", "params": {}},
        )
        assert duplicate.status_code == 400

        unknown = logged_in.post(
            "/api/v1/vendors/llms",
            json={"name": "test_api_unknown", "vendor": "NoSuchVendor", "params": {}},
        )
        assert unknown.status_code == 400

        tested = logged_in.post(
            "/api/v1/vendors/llms/test",
            json={"vendor": "ChatOpenAI", "params": {"api_key": "sk-test"}},
        )
        assert tested.status_code == 200, tested.text
        assert tested.json()["ok"] is True

        updated = logged_in.patch(
            f"/api/v1/vendors/llms/{TEST_LLM}",
            json={"new_name": f"{TEST_LLM}_renamed", "params": {"model": "gpt-4o"}},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["name"] == f"{TEST_LLM}_renamed"

        renamed = logged_in.get(f"/api/v1/vendors/llms/{TEST_LLM}_renamed").json()
        assert renamed["spec"]["model"] == "gpt-4o"
        # the vendor type survives the parameter merge
        assert renamed["spec"]["__type__"].endswith("ChatOpenAI")
    finally:
        _delete(logged_in, "llms", TEST_LLM)
        _delete(logged_in, "llms", f"{TEST_LLM}_renamed")
        for name in before:  # restore whatever was default before the test
            logged_in.patch(f"/api/v1/vendors/llms/{name}", json={"default": True})


def test_setting_a_default_model_moves_the_flag_then_restores_it(logged_in):
    before = _default_names(logged_in)
    try:
        created = logged_in.post(
            "/api/v1/vendors/llms",
            json={
                "name": TEST_LLM,
                "vendor": "ChatOpenAI",
                "params": {"api_key": "sk-test"},
                "default": True,
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["default"] is True

        defaults = _default_names(logged_in)
        assert defaults == [TEST_LLM], "exactly one default after promoting a model"
    finally:
        _delete(logged_in, "llms", TEST_LLM)
        for name in before:
            logged_in.patch(f"/api/v1/vendors/llms/{name}", json={"default": True})


def test_delete_missing_entry_is_a_404(logged_in):
    assert logged_in.delete("/api/v1/vendors/llms/nope").status_code == 404
    assert logged_in.get("/api/v1/vendors/llms/nope").status_code == 404
    assert logged_in.get("/api/v1/vendors/nope").status_code == 404


def test_embedding_create_and_delete(logged_in):
    created = logged_in.post(
        "/api/v1/vendors/embeddings",
        json={
            "name": TEST_EMBEDDING,
            "vendor": "OpenAIEmbeddings",
            "params": {"api_key": "sk-test"},
        },
    )
    assert created.status_code == 201, created.text
    try:
        assert logged_in.get(f"/api/v1/vendors/embeddings/{TEST_EMBEDDING}").status_code == 200
    finally:
        _delete(logged_in, "embeddings", TEST_EMBEDDING)
    assert logged_in.get(f"/api/v1/vendors/embeddings/{TEST_EMBEDDING}").status_code == 404


def test_mcp_server_crud(logged_in):
    created = logged_in.post(
        "/api/v1/vendors/mcp",
        json={"name": TEST_MCP, "config": {"command": "echo", "args": ["hi"]}},
    )
    assert created.status_code == 201, created.text
    try:
        entry = logged_in.get(f"/api/v1/vendors/mcp/{TEST_MCP}").json()
        assert entry["config"]["command"] == "echo"

        updated = logged_in.patch(
            f"/api/v1/vendors/mcp/{TEST_MCP}",
            json={"config": {"command": "echo", "args": ["bye"]}},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["config"]["args"] == ["bye"]
    finally:
        _delete(logged_in, "mcp", TEST_MCP)


def test_only_admins_can_change_resources(logged_in):
    created_user = logged_in.post(
        "/api/v1/users",
        json={"username": "test_vendor_plain", "password": "Abcd1234!"},
    ).json()
    try:
        other = TestClient(logged_in.app)
        assert (
            other.post(
                "/api/v1/auth/login",
                json={"username": "test_vendor_plain", "password": "Abcd1234!"},
            ).status_code
            == 200
        )
        # reading the catalog is fine for any signed-in user …
        assert other.get("/api/v1/vendors").status_code == 200
        assert other.get("/api/v1/vendors/llms").status_code == 200
        # … but not reading secrets or changing anything
        assert other.get("/api/v1/vendors/llms/ChatOpenAI").status_code == 403
        assert (
            other.post(
                "/api/v1/vendors/llms",
                json={"name": "x", "vendor": "ChatOpenAI", "params": {}},
            ).status_code
            == 403
        )
    finally:
        logged_in.delete(f"/api/v1/users/{created_user['id']}")


def test_vendor_endpoints_require_a_session(client):
    assert client.get("/api/v1/vendors").status_code == 401
    assert client.get("/api/v1/vendors/llms").status_code == 401
