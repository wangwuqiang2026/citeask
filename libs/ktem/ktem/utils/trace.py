"""Per-query trace: what a question retrieved, whether it was refused, what it cost.

An answer is a black box once the page has rendered it. This writes one JSON line per
question — retrieved count, best similarity, whether the refusal gate fired, answer
length, wall-clock time and the LLM usage that request consumed — so "why did this
answer come out like that" can be answered afterwards (ROADMAP C4), and so the cost of
a switch like ``use_llm_reranking`` can be measured instead of guessed (C3).

Off by default. Enable with ``KH_QUERY_TRACE=1`` (writes to
``ktem_app_data/query_trace.jsonl``) or point it at a file with
``KH_QUERY_TRACE=path/to/trace.jsonl``. A trace write failure never breaks an answer.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from theflow.settings import settings as flowsettings

logger = logging.getLogger(__name__)

_TRUE_VALUES = {"1", "true", "yes", "on"}


def trace_path() -> Optional[Path]:
    """Configured trace file, or ``None`` when tracing is off."""
    raw = str(getattr(flowsettings, "KH_QUERY_TRACE", "") or "").strip()
    if not raw:
        return None
    if raw.lower() in _TRUE_VALUES:
        data_dir = Path(getattr(flowsettings, "KH_APP_DATA_DIR", "."))
        return data_dir / "query_trace.jsonl"
    return Path(raw)


class TraceRecorder:
    """Append-only JSONL writer for one query."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path if path is not None else trace_path()

    @property
    def enabled(self) -> bool:
        return self._path is not None

    @property
    def path(self) -> Optional[Path]:
        return self._path

    def record(self, **fields: Any) -> Optional[dict]:
        """Write one entry; returns it so a caller (or a test) can inspect it."""
        if self._path is None:
            return None

        entry = {"time": datetime.now().isoformat(timespec="seconds"), **fields}
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:  # a trace must never break the answer path
            logger.warning("could not write the query trace %s: %s", self._path, exc)
            return None
        return entry


def read_trace(path: Optional[Path] = None) -> list[dict]:
    """Read a trace file, skipping lines that are not valid JSON."""
    resolved = path if path is not None else trace_path()
    if resolved is None or not Path(resolved).exists():
        return []

    entries = []
    for line in Path(resolved).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("skipping a malformed trace line in %s", resolved)
    return entries
