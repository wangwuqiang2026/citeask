"""Per-process LLM usage accounting.

The chat answer does not carry its token cost, so "what does one answer cost?" could
only be answered by looking at the provider's dashboard. This records what the OpenAI
compatible chat wrappers already receive (``resp["usage"]``) into a small thread-safe
counter, which the query trace snapshots per request (``ktem/utils/trace.py``) and
``tools/trace_report.py`` aggregates.

It is a *per-process* total, not per-conversation: a trace entry stores the delta
around one request, which is what the report needs.
"""

from __future__ import annotations

import threading


class UsageCounter:
    """Cumulative chat-completion usage for this process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_tokens = 0

    def add(self, prompt_tokens: int = 0, completion_tokens: int = 0, total: int = 0):
        """Record one completed chat call."""
        with self._lock:
            self._calls += 1
            self._prompt_tokens += int(prompt_tokens or 0)
            self._completion_tokens += int(completion_tokens or 0)
            self._total_tokens += int(total or 0)

    def snapshot(self) -> dict:
        """Current totals (safe to call from another thread)."""
        with self._lock:
            return {
                "calls": self._calls,
                "prompt_tokens": self._prompt_tokens,
                "completion_tokens": self._completion_tokens,
                "total_tokens": self._total_tokens,
            }

    def reset(self) -> None:
        with self._lock:
            self._calls = 0
            self._prompt_tokens = 0
            self._completion_tokens = 0
            self._total_tokens = 0

    def since(self, before: dict) -> dict:
        """Usage that happened after ``before`` (a previous snapshot)."""
        now = self.snapshot()
        return {
            key: max(0, now[key] - int(before.get(key, 0)))
            for key in ("calls", "prompt_tokens", "completion_tokens", "total_tokens")
        }


#: The process-wide counter. Reset it in tests; read it through ``since``.
usage = UsageCounter()
