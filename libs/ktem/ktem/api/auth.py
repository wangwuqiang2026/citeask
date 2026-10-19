"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ktem.services import auth as auth_service

from .deps import current_user, get_app, optional_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response) -> dict:
    application = get_app(request)
    if not application.f_user_management:
        return {"user": auth_service.anonymous_user()}

    user = auth_service.verify_user(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码无效")

    response.set_cookie(
        key=auth_service.SESSION_COOKIE,
        value=auth_service.issue_token(user["id"]),
        max_age=auth_service.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {"user": user}


@router.post("/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(auth_service.SESSION_COOKIE, path="/")
    return response


@router.get("/me")
def me(user: dict | None = Depends(optional_user)) -> dict:
    return {"user": user}


class PasswordBody(BaseModel):
    current_password: str
    new_password: str


@router.post("/password", status_code=204)
def change_password(
    body: PasswordBody, request: Request, user: dict = Depends(current_user)
) -> Response:
    """Change the signed-in user's own password."""
    from ktem.services.users import UserService

    try:
        UserService(get_app(request)).change_password(
            user["id"], body.current_password, body.new_password
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/protected")
def protected(user: dict = Depends(current_user)) -> dict:
    """Tiny probe used by tests to assert the auth dependency."""
    return {"user": user}


__all__ = ["router"]
