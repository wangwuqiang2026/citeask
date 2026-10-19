"""FastAPI dependencies shared by the API routers."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from ktem.services import auth as auth_service
from ktem.services.chat import ChatService
from ktem.services.conversations import ConversationService
from ktem.services.settings import SettingsService


def get_app(request: Request):
    """The running :class:`ktem.app.BaseApp` instance (set by ``app.py``)."""
    application = getattr(request.app.state, "ktem_app", None)
    if application is None:
        raise HTTPException(status_code=500, detail="应用尚未初始化")
    return application


def current_user(request: Request) -> dict:
    """The signed-in user, or 401 when anonymous."""
    application = get_app(request)
    if not application.f_user_management:
        return auth_service.anonymous_user()

    token = request.cookies.get(auth_service.SESSION_COOKIE)
    user = auth_service.get_user(auth_service.read_token(token))
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def optional_user(request: Request) -> dict | None:
    """The signed-in user, or ``None`` (used by ``/auth/me``)."""
    application = get_app(request)
    if not application.f_user_management:
        return auth_service.anonymous_user()
    token = request.cookies.get(auth_service.SESSION_COOKIE)
    return auth_service.get_user(auth_service.read_token(token))


def admin_required(user: dict = Depends(current_user)) -> dict:
    if not user.get("admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def conversations(request: Request) -> ConversationService:
    return ConversationService(get_app(request))


def chat_service(request: Request) -> ChatService:
    return ChatService(get_app(request))


def settings_service(request: Request) -> SettingsService:
    return SettingsService(get_app(request))


__all__ = [
    "admin_required",
    "chat_service",
    "conversations",
    "current_user",
    "get_app",
    "optional_user",
    "settings_service",
]
