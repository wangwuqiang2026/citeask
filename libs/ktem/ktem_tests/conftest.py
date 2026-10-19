"""Shared fixtures for the web API tests.

The fixture builds the real application object (index manager + settings + the
reasoning registry) but **not** the Gradio UI: ``ktem.main.App()`` is enough for
the API, and it keeps the suite fast. A test user is created when the database
does not have one, because the admin user is normally created by the Gradio user
management page, which these tests never build.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"


@pytest.fixture(scope="session")
def application():
    from theflow.settings import settings as flowsettings

    from ktem.utils.i18n import configure, load_catalog

    language = getattr(flowsettings, "KH_UI_LANGUAGE", "en")
    if language and language != "en":
        configure(language, load_catalog(language))

    from ktem.main import App

    app = App()

    from ktem.db.models import User, engine
    from ktem.services.auth import hash_password
    from sqlmodel import Session, select

    with Session(engine) as session:
        existing = session.exec(
            select(User).where(User.username_lower == ADMIN_USERNAME)
        ).first()
        if existing is None:
            session.add(
                User(
                    username=ADMIN_USERNAME,
                    username_lower=ADMIN_USERNAME,
                    password=hash_password(ADMIN_PASSWORD),
                    admin=True,
                )
            )
            session.commit()
    return app


@pytest.fixture(scope="session")
def client(application):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from ktem.api import install_routes

    api = FastAPI()
    api.state.ktem_app = application
    install_routes(api)
    with TestClient(api) as test_client:
        yield test_client


@pytest.fixture()
def logged_in(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    yield client
    client.post("/api/v1/auth/logout")
