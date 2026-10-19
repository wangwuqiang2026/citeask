"""Static assets of the UI, and the loaders the app reads them with.

The files are loaded from disk at import time of the application (not through
Gradio's ``css=``/``js=`` files API) so that a single source tree works from a
clone, from an installed package and from a frozen bundle alike.
"""

from pathlib import Path

from decouple import config

from .theme import Kotaemon as KotaemonTheme

ASSETS_DIR: Path = Path(__file__).parent
CSS_DIR: Path = ASSETS_DIR / "css"
JS_DIR: Path = ASSETS_DIR / "js"

PDFJS_VERSION_DIST: str = config("PDFJS_VERSION_DIST", "pdfjs-4.0.379-dist")
PDFJS_PREBUILT_DIR: Path = config(
    "PDFJS_PREBUILT_DIR", Path(__file__).parent / "prebuilt" / PDFJS_VERSION_DIST
)

#: Stylesheets concatenated by :func:`load_css`, in cascade order: the design
#: tokens must be declared before the rules that consume them.
CSS_FILES: tuple[str, ...] = ("tokens.css", "main.css")


def read_asset(path: str | Path) -> str:
    """Read one text asset as UTF-8 (source files contain Chinese)."""
    return Path(path).read_text(encoding="utf-8")


def load_css() -> str:
    """Return the application stylesheet: tokens first, then the rules.

    Gradio accepts a single CSS string for ``Blocks(css=...)``; keeping the
    token layer as its own file is what lets ``main.css`` stay free of literal
    colours, so the concatenation order here is load-bearing.
    """
    parts = []
    for name in CSS_FILES:
        path = CSS_DIR / name
        if not path.is_file():
            raise FileNotFoundError(f"missing stylesheet: {path}")
        parts.append(read_asset(path))
    return "\n".join(parts)


def read_js(name: str) -> str:
    """Return the contents of one JavaScript asset by file name."""
    path = JS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"missing script: {path}")
    return read_asset(path)


__all__ = [
    "ASSETS_DIR",
    "CSS_DIR",
    "CSS_FILES",
    "JS_DIR",
    "KotaemonTheme",
    "PDFJS_PREBUILT_DIR",
    "PDFJS_VERSION_DIST",
    "load_css",
    "read_asset",
    "read_js",
]
