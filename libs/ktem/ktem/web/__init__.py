"""Frontend assets of the web UI and where the host finds them.

Two locations are valid:

* ``<repo>/web/dist`` - the build a checkout produces (``npm run build``);
* ``<package>/web/dist`` - the copy shipped inside the wheel for installs.

``app.py`` asks :func:`resolve_web_dist` once, at import time.
"""

from __future__ import annotations

import os
from pathlib import Path

#: The copy that lives next to this file (inside the installed package).
PACKAGED_WEB_DIST: Path = Path(__file__).parent / "dist"


def resolve_web_dist(
    repo_root: Path | str | None = None, configured: str | None = None
) -> Path:
    """Return the directory the FastAPI host should serve at ``/``.

    Args:
        repo_root: repository root; ``<repo_root>/web/dist`` wins when it holds
            an ``index.html`` (the checkout build).
        configured: an explicit path (``KH_WEB_DIST``), which always wins.

    Returns:
        The directory to serve. It may not exist yet - the caller decides what
        to do in that case (``app.py`` falls back to the classic Gradio UI).
    """
    if configured:
        return Path(configured)

    if repo_root is not None:
        candidate = Path(repo_root) / "web" / "dist"
        if (candidate / "index.html").is_file():
            return candidate

    return PACKAGED_WEB_DIST


def env_web_dist() -> str:
    """``KH_WEB_DIST`` from the environment, or an empty string."""
    return os.environ.get("KH_WEB_DIST", "")


__all__ = ["PACKAGED_WEB_DIST", "env_web_dist", "resolve_web_dist"]
