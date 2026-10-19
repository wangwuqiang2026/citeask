"""User settings for the web API.

The settings system is already data-driven (:class:`ktem.settings.SettingItem`
carries the component, the choices and the label), so the web UI renders forms
from :meth:`SettingsService.schema` and stores flat ``key -> value`` maps through
:meth:`SettingsService.save`. Labels are translated at request time with the
catalog activated by ``app.py``, which keeps the translation source in Python.
"""

from __future__ import annotations

from typing import Any

from ktem.db.models import Settings, engine
from ktem.utils.i18n import tr
from sqlmodel import Session, select


def _choices(raw: Any) -> list[dict]:
    """Normalise ``["a", ("Label", "value")]`` into ``[{label, value}]``."""
    output: list[dict] = []
    for choice in raw or []:
        if isinstance(choice, (list, tuple)) and len(choice) == 2:
            output.append({"label": tr(str(choice[0])), "value": choice[1]})
        else:
            output.append({"label": tr(str(choice)), "value": choice})
    return output


def _item(key: str, item) -> dict:
    metadata = getattr(item, "metadata", {}) or {}
    return {
        "key": key,
        "label": tr(item.name),
        "type": item.component,
        "choices": _choices(item.choices),
        "value": item.value,
        "info": str(metadata.get("info", "")),
        "special_type": item.special_type,
    }


class SettingsService:
    """Read, write and describe the per-user settings."""

    def __init__(self, app):
        self._app = app

    # ------------------------------------------------------------------ read
    def load(self, user_id: Any) -> dict:
        defaults = self._app.default_settings.flatten()
        with Session(engine) as session:
            row = session.exec(
                select(Settings).where(Settings.user == user_id)
            ).first()
        if row is None or not isinstance(row.setting, dict):
            return defaults
        return {**defaults, **row.setting}

    def schema(self) -> dict:
        """Describe every setting as a group of form fields."""
        groups: list[dict] = []
        defaults = self._app.default_settings

        if defaults.application.settings:
            groups.append(
                {
                    "id": "application",
                    "label": tr("General"),
                    "items": [
                        _item(f"application.{key}", item)
                        for key, item in defaults.application.settings.items()
                    ],
                }
            )

        index_names = {
            index.id: index.name for index in self._app.index_manager.indices
        }
        for index_id, group in defaults.index.options.items():
            if not group.settings:
                continue
            groups.append(
                {
                    "id": f"index.options.{index_id}",
                    "label": tr(index_names.get(index_id, f"index {index_id}")),
                    "items": [
                        _item(f"index.options.{index_id}.{key}", item)
                        for key, item in group.settings.items()
                    ],
                }
            )

        if defaults.reasoning.settings:
            groups.append(
                {
                    "id": "reasoning",
                    "label": tr("Reasoning settings"),
                    "items": [
                        _item(f"reasoning.{key}", item)
                        for key, item in defaults.reasoning.settings.items()
                    ],
                }
            )

        for reasoning_id, group in defaults.reasoning.options.items():
            if not group.settings:
                continue
            label = reasoning_id
            try:
                from ktem.components import reasonings

                reasoning = reasonings.get(reasoning_id)
                if reasoning is not None:
                    label = tr(str(reasoning.get_info().get("name", reasoning_id)))
            except Exception:  # noqa: BLE001 - a label must never break the schema
                pass
            groups.append(
                {
                    "id": f"reasoning.options.{reasoning_id}",
                    "label": label,
                    "items": [
                        _item(f"reasoning.options.{reasoning_id}.{key}", item)
                        for key, item in group.settings.items()
                    ],
                }
            )

        return {"groups": groups}

    # ----------------------------------------------------------------- write
    def save(self, user_id: Any, values: dict) -> dict:
        if not isinstance(values, dict):
            raise ValueError("设置格式无效")
        with Session(engine) as session:
            row = session.exec(
                select(Settings).where(Settings.user == user_id)
            ).first()
            stored = dict(row.setting) if row and isinstance(row.setting, dict) else {}
            stored.update(values)
            if row is None:
                row = Settings(user=user_id, setting=stored)
            else:
                row.setting = stored
            session.add(row)
            session.commit()
        return self.load(user_id)


__all__ = ["SettingsService"]
