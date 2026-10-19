"""Settings endpoints: values, form schema and save."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ktem.services.settings import SettingsService

from .deps import current_user
from .deps import settings_service as settings_service_dep

router = APIRouter(prefix="/settings", tags=["settings"])


class SaveBody(BaseModel):
    values: dict


@router.get("")
def read_settings(
    service: SettingsService = Depends(settings_service_dep),
    user: dict = Depends(current_user),
) -> dict:
    return {"values": service.load(user["id"])}


@router.get("/schema")
def read_schema(
    service: SettingsService = Depends(settings_service_dep),
    user: dict = Depends(current_user),
) -> dict:
    return service.schema()


@router.put("")
def save_settings(
    body: SaveBody,
    service: SettingsService = Depends(settings_service_dep),
    user: dict = Depends(current_user),
) -> dict:
    return {"values": service.save(user["id"], body.values)}


__all__ = ["router"]
