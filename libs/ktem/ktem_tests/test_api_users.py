"""User management endpoints of the web API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import ADMIN_PASSWORD, ADMIN_USERNAME

GOOD_PASSWORD = "Abcd1234!"


def _create(client, username: str, password: str = GOOD_PASSWORD, admin: bool = False):
    return client.post(
        "/api/v1/users",
        json={"username": username, "password": password, "admin": admin},
    )


def test_users_are_listed_without_secrets(logged_in):
    response = logged_in.get("/api/v1/users")
    assert response.status_code == 200
    items = response.json()["items"]
    assert any(item["username"] == ADMIN_USERNAME and item["admin"] for item in items)
    assert all(set(item) == {"id", "username", "admin"} for item in items)


def test_create_user_then_sign_in(logged_in):
    created = _create(logged_in, "test_signin_user")
    assert created.status_code == 201, created.text
    user = created.json()
    assert user["username"] == "test_signin_user"
    assert user["admin"] is False

    try:
        other = TestClient(logged_in.app)
        response = other.post(
            "/api/v1/auth/login",
            json={"username": "TEST_signin_user", "password": GOOD_PASSWORD},
        )
        assert response.status_code == 200, response.text
        assert response.json()["user"]["username"] == "test_signin_user"
    finally:
        assert logged_in.delete(f"/api/v1/users/{user['id']}").status_code == 204


def test_create_user_validates_input(logged_in):
    assert _create(logged_in, "ab").status_code == 400  # too short
    assert _create(logged_in, "bad name").status_code == 400  # not alphanumeric
    short_password = _create(logged_in, "test_bad_password", password="abc")
    assert short_password.status_code == 400
    assert "至少" in short_password.json()["detail"]

    created = _create(logged_in, "test_duplicate")
    assert created.status_code == 201
    try:
        duplicate = _create(logged_in, "TEST_DUPLICATE")
        assert duplicate.status_code == 400
        assert "已存在" in duplicate.json()["detail"]
    finally:
        logged_in.delete(f"/api/v1/users/{created.json()['id']}")


def test_update_user_renames_and_resets_password(logged_in):
    created = _create(logged_in, "test_update_user").json()
    try:
        updated = logged_in.patch(
            f"/api/v1/users/{created['id']}",
            json={"username": "test_updated_user", "admin": True},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["username"] == "test_updated_user"
        assert updated.json()["admin"] is True

        reset = logged_in.patch(
            f"/api/v1/users/{created['id']}", json={"password": "Zxcv9876!"}
        )
        assert reset.status_code == 200, reset.text

        other = TestClient(logged_in.app)
        signed_in = other.post(
            "/api/v1/auth/login",
            json={"username": "test_updated_user", "password": "Zxcv9876!"},
        )
        assert signed_in.status_code == 200, signed_in.text
    finally:
        logged_in.delete(f"/api/v1/users/{created['id']}")


def test_admin_cannot_delete_or_demote_themselves(logged_in):
    me = logged_in.get("/api/v1/auth/me").json()["user"]

    assert logged_in.delete(f"/api/v1/users/{me['id']}").status_code == 400
    demote = logged_in.patch(f"/api/v1/users/{me['id']}", json={"admin": False})
    assert demote.status_code == 400
    assert "管理员" in demote.json()["detail"]


def test_non_admin_cannot_manage_users(logged_in):
    created = _create(logged_in, "test_plain_user").json()
    try:
        other = TestClient(logged_in.app)
        assert (
            other.post(
                "/api/v1/auth/login",
                json={"username": "test_plain_user", "password": GOOD_PASSWORD},
            ).status_code
            == 200
        )
        assert other.get("/api/v1/users").status_code == 403
        assert (
            other.post(
                "/api/v1/users",
                json={"username": "x_user", "password": GOOD_PASSWORD},
            ).status_code
            == 403
        )
    finally:
        logged_in.delete(f"/api/v1/users/{created['id']}")


def test_user_can_change_own_password(logged_in):
    created = _create(logged_in, "test_password_user").json()
    try:
        other = TestClient(logged_in.app)
        assert (
            other.post(
                "/api/v1/auth/login",
                json={"username": "test_password_user", "password": GOOD_PASSWORD},
            ).status_code
            == 200
        )

        wrong = other.post(
            "/api/v1/auth/password",
            json={"current_password": "not-the-password", "new_password": "Newpass123!"},
        )
        assert wrong.status_code == 400
        assert "当前密码" in wrong.json()["detail"]

        weak = other.post(
            "/api/v1/auth/password",
            json={"current_password": GOOD_PASSWORD, "new_password": "short"},
        )
        assert weak.status_code == 400

        changed = other.post(
            "/api/v1/auth/password",
            json={"current_password": GOOD_PASSWORD, "new_password": "Newpass123!"},
        )
        assert changed.status_code == 204

        assert (
            other.post(
                "/api/v1/auth/login",
                json={"username": "test_password_user", "password": "Newpass123!"},
            ).status_code
            == 200
        )
    finally:
        logged_in.delete(f"/api/v1/users/{created['id']}")
