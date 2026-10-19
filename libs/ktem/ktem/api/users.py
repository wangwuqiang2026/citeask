"""User management endpoints (admin only, except the password change)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ktem.services.users import UserService

from .deps import admin_required, get_app

router = APIRouter(prefix="/users", tags=["users"])


class CreateUserBody(BaseModel):
    username: str
    password: str
    admin: bool = False


class UpdateUserBody(BaseModel):
    username: str | None = None
    password: str | None = None
    admin: bool | None = None


def _service(request: Request) -> UserService:
    return UserService(get_app(request))


def _translate(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        message = error.args[0] if error.args else "用户不存在"
        return HTTPException(status_code=404, detail=str(message))
    if isinstance(error, PermissionError):
        message = error.args[0] if error.args else "没有权限"
        return HTTPException(status_code=400, detail=str(message))
    return HTTPException(status_code=400, detail=str(error))


@router.get("")
def list_users(
    request: Request, _: dict = Depends(admin_required)
) -> dict:
    return {"items": _service(request).list()}


@router.post("", status_code=201)
def create_user(
    body: CreateUserBody, request: Request, _: dict = Depends(admin_required)
) -> dict:
    try:
        return _service(request).create(body.username, body.password, body.admin)
    except (ValueError, KeyError, PermissionError) as exc:
        raise _translate(exc) from exc


@router.patch("/{user_id}")
def update_user(
    user_id: str,
    body: UpdateUserBody,
    request: Request,
    user: dict = Depends(admin_required),
) -> dict:
    try:
        return _service(request).update(
            user_id,
            username=body.username,
            password=body.password,
            admin=body.admin,
            acting_user_id=user["id"],
        )
    except (ValueError, KeyError, PermissionError) as exc:
        raise _translate(exc) from exc


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: str, request: Request, user: dict = Depends(admin_required)
) -> Response:
    try:
        _service(request).delete(user_id, acting_user_id=user["id"])
    except (ValueError, KeyError, PermissionError) as exc:
        raise _translate(exc) from exc
    return Response(status_code=204)


__all__ = ["router"]
