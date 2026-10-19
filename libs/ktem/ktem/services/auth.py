"""Authentication helpers for the web API.

The classic Gradio UI keeps the signed-in user in its own browser state; the web
UI needs a real server-side session. The cookie is an HMAC-signed
``user_id|issued_at`` pair - no server-side session table, no extra dependency.

The secret comes from ``KH_SESSION_SECRET`` when set. Otherwise it is generated
once and persisted under ``ktem_app_data/session.key`` so restarts keep existing
sessions valid (the directory is git-ignored).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

from ktem.db.models import User, engine
from sqlmodel import Session, select
from theflow.settings import settings as flowsettings

#: Cookie carrying the signed session.
SESSION_COOKIE = "ktem_session"
#: How long a session stays valid, in seconds.
SESSION_MAX_AGE = 7 * 24 * 60 * 60

_SECRET_FILE = Path(str(getattr(flowsettings, "KH_APP_DATA_DIR", "."))) / "session.key"
_SECRET_CACHE: bytes | None = None


def _secret() -> bytes:
    """The signing key: configuration first, persisted random key otherwise."""
    global _SECRET_CACHE
    if _SECRET_CACHE is not None:
        return _SECRET_CACHE

    configured = os.environ.get("KH_SESSION_SECRET") or getattr(
        flowsettings, "KH_SESSION_SECRET", ""
    )
    if configured:
        _SECRET_CACHE = str(configured).encode("utf-8")
        return _SECRET_CACHE

    try:
        if _SECRET_FILE.exists():
            value = _SECRET_FILE.read_text(encoding="utf-8").strip()
            if value:
                _SECRET_CACHE = value.encode("utf-8")
                return _SECRET_CACHE
    except OSError:
        pass

    value = secrets.token_urlsafe(48)
    try:
        _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SECRET_FILE.write_text(value, encoding="utf-8")
    except OSError as exc:  # read-only install: sessions are still valid this run
        print(f"warning: could not persist {_SECRET_FILE}: {exc}")
    _SECRET_CACHE = value.encode("utf-8")
    return _SECRET_CACHE


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_token(user_id: str) -> str:
    """Create the cookie value for ``user_id``."""
    payload = f"{user_id}|{int(time.time())}"
    return f"{payload}|{_sign(payload)}"


def read_token(token: str | None) -> str | None:
    """Return the user id carried by ``token``, or ``None`` when it is invalid."""
    if not token:
        return None
    parts = token.split("|")
    if len(parts) != 3:
        return None
    user_id, issued_at, signature = parts
    payload = f"{user_id}|{issued_at}"
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        issued = int(issued_at)
    except ValueError:
        return None
    if time.time() - issued > SESSION_MAX_AGE:
        return None
    return user_id


def hash_password(password: str) -> str:
    """Password hash used by the existing user table."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_user(username: str, password: str) -> dict | None:
    """Return ``{id, username, admin}`` for valid credentials, else ``None``."""
    if not username or not password:
        return None
    with Session(engine) as session:
        statement = select(User).where(User.username_lower == username.lower().strip())
        user = session.exec(statement).first()
    if user is None:
        return None
    if not hmac.compare_digest(user.password, hash_password(password)):
        return None
    return {"id": user.id, "username": user.username, "admin": bool(user.admin)}


def get_user(user_id: str | None) -> dict | None:
    """Look a user up by id (used by the auth dependency on every request)."""
    if not user_id:
        return None
    with Session(engine) as session:
        user = session.exec(select(User).where(User.id == user_id)).first()
    if user is None:
        return None
    return {"id": user.id, "username": user.username, "admin": bool(user.admin)}


def anonymous_user() -> dict:
    """Identity used when user management is disabled."""
    return {"id": 1, "username": "default", "admin": True}


__all__ = [
    "SESSION_COOKIE",
    "SESSION_MAX_AGE",
    "anonymous_user",
    "get_user",
    "hash_password",
    "issue_token",
    "read_token",
    "verify_user",
]
