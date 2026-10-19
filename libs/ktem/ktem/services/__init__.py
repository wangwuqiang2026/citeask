"""Service layer of the HTTP API.

The modules here hold the application logic behind ``/api/v1`` and are free of
Gradio imports: the classic UI in ``ktem.pages`` keeps its own copy of the
orchestration until it is retired, while the pipelines themselves are shared.
"""

from __future__ import annotations

from . import auth, chat, conversations, settings  # noqa: F401

__all__ = ["auth", "chat", "conversations", "settings"]
