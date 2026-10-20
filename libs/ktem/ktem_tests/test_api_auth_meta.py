"""Auth, meta and settings endpoints of the web API."""

from __future__ import annotations

from theflow.settings import settings as flowsettings

from .conftest import ADMIN_PASSWORD, ADMIN_USERNAME


def test_anonymous_requests_are_rejected(client):
    assert client.get("/api/v1/conversations").status_code == 401
    assert client.get("/api/v1/meta").status_code == 401
    assert client.get("/api/v1/auth/me").json() == {"user": None}


def test_login_with_wrong_password_is_rejected(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": ADMIN_USERNAME, "password": "nope"}
    )
    assert response.status_code == 401


def test_login_sets_a_session_and_me_returns_the_user(logged_in):
    payload = logged_in.get("/api/v1/auth/me").json()
    assert payload["user"]["username"] == ADMIN_USERNAME
    assert payload["user"]["admin"] is True


def test_logout_clears_the_session(client):
    client.post(
        "/api/v1/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert client.get("/api/v1/auth/me").json()["user"] is not None
    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/me").json()["user"] is None


def test_meta_describes_the_application(logged_in):
    meta = logged_in.get("/api/v1/meta").json()

    assert meta["app"]["name"]
    assert meta["indices"], "the fixture index should be listed"
    assert meta["reasoning"]["choices"], "reasoning modes must be offered"
    assert meta["languages"]["choices"], "languages must be offered"
    assert meta["models"]["choices"][0]["value"] == ""

    # The active model is a real pool entry, not the hard-coded "" placeholder:
    # the frontend shows it as the model the user is running on (MODIFICATIONS §5.33).
    # A fresh install with no configured provider has an empty pool instead (§5.34).
    choice_values = {item["value"] for item in meta["models"]["choices"]}
    default_model = meta["models"]["default"]
    assert default_model in choice_values
    assert (default_model != "") == bool(choice_values - {""})

    if getattr(flowsettings, "KH_UI_LANGUAGE", "en") == "zh":
        labels = {item["label"] for item in meta["reasoning"]["choices"]}
        assert "简单问答" in labels, "reasoning labels must be localized"


def test_settings_schema_and_round_trip(logged_in):
    schema = logged_in.get("/api/v1/settings/schema").json()
    assert schema["groups"], "settings must be described as form groups"

    keys = [item["key"] for group in schema["groups"] for item in group["items"]]
    assert all("." in key for key in keys)
    assert any(key.startswith("reasoning.") for key in keys)

    before = logged_in.get("/api/v1/settings").json()["values"]
    key = "reasoning.lang"
    assert key in before
    original = before[key]
    replacement = "en" if original != "en" else "zh"

    saved = logged_in.put("/api/v1/settings", json={"values": {key: replacement}})
    assert saved.status_code == 200
    assert saved.json()["values"][key] == replacement
    assert logged_in.get("/api/v1/settings").json()["values"][key] == replacement

    logged_in.put("/api/v1/settings", json={"values": {key: original}})
