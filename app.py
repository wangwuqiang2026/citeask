import os

from theflow.settings import settings as flowsettings

KH_APP_DATA_DIR = getattr(flowsettings, "KH_APP_DATA_DIR", ".")
KH_GRADIO_SHARE = getattr(flowsettings, "KH_GRADIO_SHARE", False)
KH_UI_LANGUAGE = getattr(flowsettings, "KH_UI_LANGUAGE", "en")
KH_UI_TRANSLATOR = getattr(flowsettings, "KH_UI_TRANSLATOR", "mymemory")
KH_UI_TRANSLATE_MISSING = getattr(flowsettings, "KH_UI_TRANSLATE_MISSING", False)
GRADIO_TEMP_DIR = os.getenv("GRADIO_TEMP_DIR", None)
# override GRADIO_TEMP_DIR if it's not set
if GRADIO_TEMP_DIR is None:
    GRADIO_TEMP_DIR = os.path.join(KH_APP_DATA_DIR, "gradio_tmp")
    os.environ["GRADIO_TEMP_DIR"] = GRADIO_TEMP_DIR


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

demo.queue().launch(
    favicon_path=app._favicon,
    inbrowser=True,
    allowed_paths=[
        "libs/ktem/ktem/assets",
        GRADIO_TEMP_DIR,
    ],
    share=KH_GRADIO_SHARE,
)
