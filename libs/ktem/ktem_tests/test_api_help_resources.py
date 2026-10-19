"""Read-only resources and bundled help documents."""

from __future__ import annotations


def test_resources_list_indices_and_model_pools(logged_in):
    response = logged_in.get("/api/v1/resources")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["indices"], "the fixture index should be listed"
    index = payload["indices"][0]
    assert set(index) == {"id", "name", "private", "file_count"}

    for pool in ("llms", "embeddings", "rerankings"):
        assert isinstance(payload[pool], list)
        for row in payload[pool]:
            assert set(row) == {"name", "vendor", "model", "default"}
            assert isinstance(row["default"], bool)

    # The specs carry API keys; the endpoint must only expose the vendor class.
    assert "api_key" not in response.text
    assert "spec" not in response.text


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
