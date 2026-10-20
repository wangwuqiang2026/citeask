"""The built-in model presets: seed only what is configured (MODIFICATIONS §5.34).

Upstream seeds every vendor template from ``flowsettings.KH_LLMS`` into the model
pool on first run. Most of those templates still carry placeholder credentials
(``your-key`` / ``<YOUR_OPENAI_KEY>``), so the resources page listed providers the
user never configured and could not use.

This module replaces "write the template list" with "keep the user's model pool":
a preset is inserted only when its required secrets are real, and a template row
that still carries placeholder credentials is removed. A row whose spec differs
from the template is left alone — it belongs to the user.
"""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ktem.db.engine import engine

#: Parameter names that carry credentials (the vendor ``describe()`` metadata does
#: not mark them as secret, so the name is the only signal).
_SECRET_HINTS = ("key", "token", "secret", "password")

#: Values that are shipped as examples rather than real credentials.
_PLACEHOLDER_HINTS = (
    "your-key",
    "your_key",
    "your-key-here",
    "<your",
    "changeme",
    "placeholder",
)


def _is_secret(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in _SECRET_HINTS)


def _is_placeholder(value: Any) -> bool:
    """Whether a credential is missing, an example value, or an unset marker."""
    if value is None:
        return True
    if isinstance(value, dict):
        # theflow's unset sentinel is a dict with a type name containing "unset_"
        return "unset" in str(value.get("__type__", "")).lower()
    if not isinstance(value, str):
        return False
    text = value.strip().lower()
    if not text:
        return True
    return any(hint in text for hint in _PLACEHOLDER_HINTS)


def is_configured(spec: dict) -> bool:
    """Whether a preset spec names a model the user can actually run.

    A vendor that has required secret parameters must have real values for all of
    them; a local vendor with no required secrets (``LocalLexicalReranker``,
    ``FastEmbedEmbeddings`` …) is configured as it is. An unloadable vendor is not
    configured: guessing would put a broken entry in front of the user.
    """
    from theflow.utils.modules import import_dotted_string

    type_path = (spec or {}).get("__type__")
    if not type_path:
        return False
    try:
        vendor = import_dotted_string(str(type_path), safe=False)
        params = (vendor.describe() or {}).get("params") or {}
    except Exception:  # noqa: BLE001 - an unknown/broken vendor is not usable
        return False

    for name, meta in params.items():
        if not _is_secret(name) or not meta.get("required", False):
            continue
        value = spec.get(name, meta.get("default"))
        if _is_placeholder(value):
            return False
    return True


def sync_presets(
    table,
    presets: dict,
    *,
    session: Session | None = None,
) -> dict[str, list[str]]:
    """Reconcile one model table with the shipped presets.

    Args:
        table: the SQLAlchemy model class (``LLMTable`` …).
        presets: the ``flowsettings.KH_<KIND>`` mapping (``name -> {"spec", …}``).
        session: optional session for tests; the app data engine is used otherwise.

    Returns:
        ``{"seeded": [...], "pruned": [...]}`` for logging and tests.
    """
    report: dict[str, list[str]] = {"seeded": [], "pruned": []}
    context = nullcontext(session) if session is not None else Session(engine)
    with context as sess:
        rows = {row.name: row for row in sess.execute(select(table)).scalars()}
        for name, preset in (presets or {}).items():
            spec = (preset or {}).get("spec") or {}
            configured = is_configured(spec)
            row = rows.get(name)
            if row is not None:
                if not configured and row.spec == spec:
                    sess.delete(row)
                    report["pruned"].append(name)
                continue
            if configured:
                sess.add(
                    table(
                        name=name,
                        spec=spec,
                        default=bool((preset or {}).get("default", False)),
                    )
                )
                report["seeded"].append(name)
        sess.commit()
    return report


__all__ = ["is_configured", "sync_presets"]
