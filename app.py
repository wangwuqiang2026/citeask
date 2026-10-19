import asyncio
import os
import threading
import webbrowser
from pathlib import Path

from theflow.settings import settings as flowsettings

KH_APP_DATA_DIR = getattr(flowsettings, "KH_APP_DATA_DIR", ".")
KH_GRADIO_SHARE = getattr(flowsettings, "KH_GRADIO_SHARE", False)
KH_OPEN_BROWSER_ON_START = getattr(flowsettings, "KH_OPEN_BROWSER_ON_START", True)
KH_UI_LANGUAGE = getattr(flowsettings, "KH_UI_LANGUAGE", "en")
KH_UI_TRANSLATOR = getattr(flowsettings, "KH_UI_TRANSLATOR", "mymemory")
KH_UI_TRANSLATE_MISSING = getattr(flowsettings, "KH_UI_TRANSLATE_MISSING", False)
# The stored uploads: the citation preview links point at the copy kept here, so the
# `/file=` route has to be allowed to serve this directory (MODIFICATIONS §5.12).
KH_FILESTORAGE_PATH = getattr(flowsettings, "KH_FILESTORAGE_PATH", "")
# The web UI is the default. Set KH_WEB_UI=0 to serve only the classic Gradio app at
# the root path - the rollback switch for the React migration (MODIFICATIONS §5.25).
KH_WEB_UI = getattr(flowsettings, "KH_WEB_UI", True)
GRADIO_TEMP_DIR = os.getenv("GRADIO_TEMP_DIR", None)
# override GRADIO_TEMP_DIR if it's not set
if GRADIO_TEMP_DIR is None:
    GRADIO_TEMP_DIR = os.path.join(KH_APP_DATA_DIR, "gradio_tmp")
    os.environ["GRADIO_TEMP_DIR"] = GRADIO_TEMP_DIR

#: Built React application. The checkout builds into ``web/dist`` (a shell process
#: in this sandbox cannot write under ``libs/``); a packaged install ships the same
#: files as ``ktem/web/dist/*``, so both locations are checked. KH_WEB_DIST wins.
from ktem.web import resolve_web_dist  # noqa: E402

WEB_DIST = resolve_web_dist(
    Path(__file__).resolve().parent,
    os.environ.get("KH_WEB_DIST") or getattr(flowsettings, "KH_WEB_DIST", ""),
)


from ktem.main import App  # noqa
from ktem.utils.i18n import (  # noqa
    bootstrap_js,
    collect_display_strings,
    collect_source_strings,
    configure,
    fill_catalog,
    install_hooks,
    load_catalog,
    localize_blocks,
    make_backend,
)

# The authoring language of the UI needs no work at all.
USE_I18N = bool(KH_UI_LANGUAGE) and KH_UI_LANGUAGE != "en"

# Activate before the UI is built: the catalog is needed by the browser bootstrap
# and by the runtime helpers (toasts, reference headers) used by the callbacks.
# load_catalog merges the catalog shipped in the repository (a fresh clone is
# Chinese out of the box) with the user's one, which overrides entry by entry.
if USE_I18N:
    _catalog = load_catalog(KH_UI_LANGUAGE)
    configure(KH_UI_LANGUAGE, _catalog)

app = App()
# Always published, and injected into <head>: main.js calls __KTEM_t
# unconditionally, and in the authoring language it is an identity function.
app.set_head_script(bootstrap_js(KH_UI_LANGUAGE))
demo = app.make()

if USE_I18N:
    install_hooks()
    # Two sources: what the built UI displays, and what is only produced later
    # (toast messages, reference headers, strings assembled by the browser).
    _strings = collect_display_strings(demo.blocks, collect_source_strings())
    _missing = _catalog.missing(_strings)

    if _missing and KH_UI_TRANSLATE_MISSING:
        print(
            f"UI language '{KH_UI_LANGUAGE}': translating {len(_missing)} missing "
            f"strings via {KH_UI_TRANSLATOR} (this takes a while) ..."
        )
        fill_catalog(
            _catalog, _strings, make_backend(KH_UI_TRANSLATOR, KH_UI_LANGUAGE)
        )
        _missing = _catalog.missing(_strings)

    _localized = localize_blocks(demo.blocks, _catalog.translations)
    print(
        f"UI language '{KH_UI_LANGUAGE}': {_localized} labels localized, "
        f"{len(_catalog.translations)} catalog entries, {len(_missing)} missing"
    )
    if _missing:
        print(
            "  run `.venv/Scripts/python.exe -m ktem.utils.i18n build "
            f"--language {KH_UI_LANGUAGE} --backend {KH_UI_TRANSLATOR}` to fill them"
        )


def _allowed_paths() -> list[str]:
    """Directories Gradio may serve with its ``/file=`` route.

    Gradio requires absolute paths here; the classic UI previously passed a
    repository-relative one that only worked when the app was started from the
    checkout (MODIFICATIONS §5.25).
    """
    paths = [str(Path(__file__).resolve().parent / "libs" / "ktem" / "ktem" / "assets")]
    paths.append(str(Path(GRADIO_TEMP_DIR).resolve()))
    if KH_FILESTORAGE_PATH:
        paths.append(str(Path(KH_FILESTORAGE_PATH).resolve()))
    if WEB_DIST.is_dir():
        paths.append(str(WEB_DIST.resolve()))
    return paths


def create_app():
    """Build the FastAPI host: JSON/SSE API + web UI + the classic Gradio app.

    The React application lives at ``/``; Gradio is mounted at ``/legacy`` while
    the pages are migrated one by one. ``KH_WEB_UI=0`` reverses that and keeps
    Gradio at the root path, which is the rollback switch.
    """
    import gradio as gr
    import uvicorn
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles

    api = FastAPI(title=app.app_name, docs_url=None, redoc_url=None)
    api.state.ktem_app = app

    from ktem.api import install_routes

    install_routes(api)

    # ---------------------------------------------------------------- api ----
    @api.get("/api/v1/health")
    def health() -> dict:
        return {
            "status": "ok",
            "app": app.app_name,
            "version": app.app_version,
            "ui": "web" if KH_WEB_UI else "classic",
        }

    @api.get("/favicon.ico")
    def favicon() -> FileResponse:
        """Serve the favicon from the root: the classic UI asks for it there."""
        return FileResponse(app._favicon)

    @api.get("/api/v1/_echo")
    async def echo() -> StreamingResponse:
        """SSE smoke test: proves event streaming works end to end."""

        async def events():
            for index in range(3):
                yield f"event: ping\ndata: {{\"index\": {index}}}\n\n"
                await asyncio.sleep(0.05)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ------------------------------------------------------------- gradio ----
    demo.queue()
    if KH_WEB_UI and WEB_DIST.is_dir():
        api = gr.mount_gradio_app(
            api,
            demo,
            path="/legacy",
            allowed_paths=_allowed_paths(),
            show_error=True,
        )
    else:
        if KH_WEB_UI:
            print(f"web UI not found at {WEB_DIST}; serving the classic UI at /")
        api = gr.mount_gradio_app(
            api,
            demo,
            path="/",
            allowed_paths=_allowed_paths(),
            show_error=True,
        )

    # ---------------------------------------------------------------- spa ----
    if KH_WEB_UI and WEB_DIST.is_dir():
        @api.get("/legacy")
        def legacy_root():
            """``/legacy`` without the trailing slash is not matched by the mount."""
            return RedirectResponse(url="/legacy/")

        assets_dir = WEB_DIST / "assets"
        if assets_dir.is_dir():
            api.mount("/assets", StaticFiles(directory=assets_dir), name="spa-assets")

        @api.get("/{full_path:path}")
        async def spa_files(full_path: str):
            """Serve the built SPA, falling back to ``index.html`` for routes."""
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404)

            index = WEB_DIST / "index.html"
            if not full_path:
                return FileResponse(index)

            candidate = (WEB_DIST / full_path).resolve()
            dist_root = WEB_DIST.resolve()
            try:
                inside = candidate.is_relative_to(dist_root)
            except AttributeError:  # Python < 3.9
                inside = str(candidate).startswith(str(dist_root))
            if inside and candidate.is_file():
                return FileResponse(candidate)

            if index.is_file():
                return FileResponse(index)
            raise HTTPException(status_code=404)

    return api


def main() -> None:
    import uvicorn

    host = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
    port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    url = f"http://{host}:{port}"
    print(f"citeask web UI: {url}" + ("  (classic: /legacy)" if KH_WEB_UI else ""))
    if KH_GRADIO_SHARE:
        print("share links are not supported by the web host; GRADIO_SERVER_SHARE ignored")

    if KH_OPEN_BROWSER_ON_START:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
