"""User records for the web API.

The rules mirror the classic user-management page: usernames are case
insensitive and restricted to alphanumerics plus underscores; passwords need a
minimum length, both letter cases, a digit and a special character. Passwords
are the same sha256 hex digest the ``User`` table has always stored, so users
created here can sign in to the classic UI and vice versa.
"""

from __future__ import annotations

import hmac
from typing import Any

from ktem.db.models import User, engine
from sqlmodel import Session, select

from .auth import hash_password

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 32
PASSWORD_MIN_LENGTH = 8
SPECIAL_CHARACTERS = "^$*.[]{}()?-\"!@#%&/\\,><':;|_~+="


def validate_username(username: str) -> str:
    """Return a human readable error, or ``""`` when the name is acceptable."""
    name = (username or "").strip()
    if len(name) < USERNAME_MIN_LENGTH:
        return f"用户名至少需要 {USERNAME_MIN_LENGTH} 个字符"
    if len(name) > USERNAME_MAX_LENGTH:
        return f"用户名最多 {USERNAME_MAX_LENGTH} 个字符"
    if not name.replace("_", "").isalnum():
        return "用户名只能包含字母、数字和下划线"
    return ""


def validate_password(password: str) -> str:
    """Return a human readable error, or ``""`` when the password is acceptable."""
    if len(password or "") < PASSWORD_MIN_LENGTH:
        return f"密码至少需要 {PASSWORD_MIN_LENGTH} 个字符"
    if not any(char.isupper() for char in password):
        return "密码需要包含至少一个大写字母"
    if not any(char.islower() for char in password):
        return "密码需要包含至少一个小写字母"
    if not any(char.isdigit() for char in password):
        return "密码需要包含至少一个数字"
    if not any(char in SPECIAL_CHARACTERS for char in password):
        return "密码需要包含至少一个特殊字符（如 ! @ # $ % 等）"
    return ""


def _row(user: User) -> dict:
    return {"id": user.id, "username": user.username, "admin": bool(user.admin)}


class UserService:
    """List, create, update and delete user records."""

    def __init__(self, app):
        self._app = app

    # ------------------------------------------------------------------ read
    def list(self) -> list[dict]:
        with Session(engine) as session:
            users = session.exec(select(User).order_by(User.username)).all()
        return [_row(user) for user in users]

    def get(self, user_id: Any) -> dict:
        with Session(engine) as session:
            user = session.exec(select(User).where(User.id == user_id)).first()
        if user is None:
            raise KeyError("用户不存在")
        return _row(user)

    # ----------------------------------------------------------------- write
    def create(self, username: str, password: str, admin: bool = False) -> dict:
        name = (username or "").strip()
        error = validate_username(name) or validate_password(password)
        if error:
            raise ValueError(error)

        with Session(engine) as session:
            existing = session.exec(
                select(User).where(User.username_lower == name.lower())
            ).first()
            if existing is not None:
                raise ValueError("用户名已存在")
            user = User(
                username=name,
                username_lower=name.lower(),
                password=hash_password(password),
                admin=bool(admin),
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return _row(user)

    def update(
        self,
        user_id: Any,
        *,
        username: str | None = None,
        password: str | None = None,
        admin: bool | None = None,
        acting_user_id: Any = None,
    ) -> dict:
        with Session(engine) as session:
            user = session.exec(select(User).where(User.id == user_id)).first()
            if user is None:
                raise KeyError("用户不存在")

            if username is not None and username.strip() != user.username:
                name = username.strip()
                error = validate_username(name)
                if error:
                    raise ValueError(error)
                clash = session.exec(
                    select(User).where(
                        User.username_lower == name.lower(), User.id != user.id
                    )
                ).first()
                if clash is not None:
                    raise ValueError("用户名已存在")
                user.username = name
                user.username_lower = name.lower()

            if password:
                error = validate_password(password)
                if error:
                    raise ValueError(error)
                user.password = hash_password(password)

            if admin is not None and bool(admin) != bool(user.admin):
                if not admin:
                    if acting_user_id is not None and user.id == acting_user_id:
                        raise PermissionError("不能取消自己的管理员权限")
                    if self._is_last_admin(session, user.id):
                        raise PermissionError("至少需要保留一个管理员")
                user.admin = bool(admin)

            session.add(user)
            session.commit()
            session.refresh(user)
            return _row(user)

    def delete(self, user_id: Any, acting_user_id: Any = None) -> None:
        with Session(engine) as session:
            user = session.exec(select(User).where(User.id == user_id)).first()
            if user is None:
                raise KeyError("用户不存在")
            if acting_user_id is not None and user.id == acting_user_id:
                raise PermissionError("不能删除当前登录的用户")
            if user.admin and self._is_last_admin(session, user.id):
                raise PermissionError("至少需要保留一个管理员")
            session.delete(user)
            session.commit()

    def change_password(
        self, user_id: Any, current_password: str, new_password: str
    ) -> None:
        with Session(engine) as session:
            user = session.exec(select(User).where(User.id == user_id)).first()
            if user is None:
                raise KeyError("用户不存在")
            if not hmac.compare_digest(user.password, hash_password(current_password)):
                raise ValueError("当前密码不正确")

            error = validate_password(new_password)
            if error:
                raise ValueError(error)
            if current_password == new_password:
                raise ValueError("新密码不能与当前密码相同")

            user.password = hash_password(new_password)
            session.add(user)
            session.commit()

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _is_last_admin(session: Session, user_id: Any) -> bool:
        admins = session.exec(select(User).where(User.admin == True)).all()  # noqa: E712
        return len(admins) <= 1 and any(user.id == user_id for user in admins)


__all__ = [
    "PASSWORD_MIN_LENGTH",
    "SPECIAL_CHARACTERS",
    "USERNAME_MAX_LENGTH",
    "USERNAME_MIN_LENGTH",
    "UserService",
    "validate_password",
    "validate_username",
]
