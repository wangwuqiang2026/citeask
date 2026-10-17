"""Tests for the translation-backed UI localization helpers.

The translation service itself is never called: a fake backend is injected, so
the suite stays offline and fast.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from ktem.utils.i18n import (
    DEFAULT_LANGUAGE,
    MAX_STRING_LENGTH,
    TranslationCatalog,
    collect_display_strings,
    fill_catalog,
    localize_blocks,
    translate_choices,
)


class Button:
    def __init__(self, value: str) -> None:
        self.value = value


class Textbox:
    def __init__(self, label: str, value: str, placeholder: str = ""):
        self.label = label
        self.value = value
        self.placeholder = placeholder


class Code:
    def __init__(self, label: str, value: str) -> None:
        self.label = label
        self.value = value


class Radio:
    def __init__(self, label: str, choices: Any, value: Any) -> None:
        self.label = label
        self.choices = choices
        self.value = value


class Dataframe:
    def __init__(self, headers: list[str]) -> None:
        self.headers = headers


class State:
    def __init__(self, value: Any) -> None:
        self.value = value


def fake_backend(text: str) -> str:
    """Deterministic stand-in for the online service."""
    return "译:" + text


def test_collect_finds_display_strings() -> None:
    """Labels, placeholders, headers and choice labels are collected."""
    blocks = {
        1: Button("Delete"),
        2: Textbox("QA Prompt", "data", placeholder="Type here"),
        3: Dataframe(["id", "name"]),
        4: Radio("Correctness:", [("Yes", "correct")], "correct"),
    }
    found = collect_display_strings(blocks)

    for expected in ("Delete", "QA Prompt", "Type here", "id", "name", "Yes"):
        assert expected in found
    # a value that is real data must never be offered for translation
    assert "data" not in found


def test_collect_skips_long_and_already_translated_strings() -> None:
    """Long payloads and strings that already contain CJK are not sent."""
    blocks = {
        1: Button("x" * (MAX_STRING_LENGTH + 1)),
        2: Button("Delete"),
        3: Button("\u5220\u9664"),
    }
    found = collect_display_strings(blocks)
    assert "x" * (MAX_STRING_LENGTH + 1) not in found
    assert "\u5220\u9664" not in found
    assert "Delete" in found


def test_collect_ignores_state_values() -> None:
    """State components hold data, never display text."""
    found = collect_display_strings({1: State({"prompt": "hello"})})
    assert "hello" not in found
    assert all(isinstance(text, str) for text in found)


def test_choice_values_are_preserved_when_labels_are_translated() -> None:
    """Translating a choice must keep the value the backend matches on."""
    choices = [("Search All", "all"), ("Search In File(s)", "select")]
    translated = translate_choices(choices, {"Search All": "\u68c0\u7d22\u5168\u90e8"})
    assert [value for _, value in translated] == ["all", "select"]
    assert translated[0][0] == "\u68c0\u7d22\u5168\u90e8"


def _values(choices: Any) -> list[Any]:
    """The value of each choice, whichever shape it takes."""
    return [item if isinstance(item, str) else item[1] for item in choices]


def _labels(choices: Any) -> list[Any]:
    """The displayed label of each choice, whichever shape it takes."""
    return [item if isinstance(item, str) else item[0] for item in choices]


def test_bare_string_choices_keep_their_value() -> None:
    """A bare string doubles as its own value, so it must survive as the value."""
    translated = translate_choices(["vector", "text"], {"vector": "\u5411\u91cf"})
    assert _values(translated) == ["vector", "text"]
    assert _labels(translated) == ["\u5411\u91cf", "text"]


def test_translate_choices_is_a_no_op_without_translations() -> None:
    choices = ["alpha", "beta"]
    assert translate_choices(choices, {}) is choices


def test_localize_blocks_only_touches_display_attributes() -> None:
    """Input components keep their data; only captions are rewritten."""
    blocks = {
        1: Button("Delete"),
        2: Textbox("QA Prompt", "Answer: {question}"),
        3: Code("Configuration (JSON)", '{"a": 1}'),
        4: Radio("Correctness:", [("Yes", "correct")], "correct"),
        5: Dataframe(["id", "name"]),
    }
    translations = {
        "Delete": "\u5220\u9664",
        "QA Prompt": "\u95ee\u7b54\u63d0\u793a\u8bcd",
        "Configuration (JSON)": "\u914d\u7f6e\uff08JSON\uff09",
        "Correctness:": "\u6b63\u786e\u6027\uff1a",
        "Yes": "\u662f",
        "id": "ID",
        "name": "\u540d\u79f0",
    }

    changed = localize_blocks(blocks, translations)

    assert changed > 0
    assert blocks[1].value == "\u5220\u9664"
    assert blocks[2].label == "\u95ee\u7b54\u63d0\u793a\u8bcd"
    # payloads of input components must stay untouched
    assert blocks[2].value == "Answer: {question}"
    assert blocks[3].value == '{"a": 1}'
    assert blocks[3].label == "\u914d\u7f6e\uff08JSON\uff09"
    assert blocks[4].choices == [("\u662f", "correct")]
    assert blocks[4].value == "correct"
    assert blocks[5].headers == ["ID", "\u540d\u79f0"]


def test_localize_blocks_without_translations_is_a_no_op() -> None:
    blocks = {1: Button("Delete")}
    assert localize_blocks(blocks, {}) == 0
    assert blocks[1].value == "Delete"


def test_catalog_round_trip(tmp_path) -> None:
    """A catalog survives a save/load cycle and reports what is missing."""
    path = tmp_path / "zh.json"
    catalog = TranslationCatalog(path)
    catalog.translations = {"Delete": "\u5220\u9664"}
    catalog.save()

    reloaded = TranslationCatalog(path).load()
    assert reloaded.lookup("Delete") == "\u5220\u9664"
    assert reloaded.lookup("Cancel") == "Cancel"
    assert reloaded.missing(["Delete", "Cancel"]) == ["Cancel"]
    assert json.loads(path.read_text(encoding="utf-8")) == {"Delete": "\u5220\u9664"}


def test_catalog_tolerates_a_missing_file(tmp_path) -> None:
    catalog = TranslationCatalog(tmp_path / "absent.json").load()
    assert catalog.translations == {}
    assert catalog.lookup("Delete") == "Delete"


def test_conflicting_translations_are_dropped(tmp_path) -> None:
    """Two different sources claiming the same translation are both discarded.

    Context-free translation collapses look-alike labels (a language selector
    where both ``English`` and ``Chinese`` become ``中文``); keeping either would
    show a duplicated, wrong entry.
    """
    from ktem.utils.i18n import drop_conflicting_translations

    catalog = TranslationCatalog(tmp_path / "zh.json")
    catalog.translations = {
        "English": "\u4e2d\u6587",
        "Chinese": "\u4e2d\u6587",
        "Delete": "\u5220\u9664",
    }

    dropped = drop_conflicting_translations(catalog)

    assert sorted(dropped) == ["Chinese", "English"]
    assert catalog.translations == {"Delete": "\u5220\u9664"}


def test_case_variants_are_not_treated_as_conflicts(tmp_path) -> None:
    """`Admin` and `admin` are the same label, so they may share a translation."""
    from ktem.utils.i18n import drop_conflicting_translations

    catalog = TranslationCatalog(tmp_path / "zh.json")
    catalog.translations = {
        "Admin": "\u7ba1\u7406\u5458",
        "admin": "\u7ba1\u7406\u5458",
        "Files": "\u6587\u4ef6",
        "files": "\u6587\u4ef6\u6570",
    }

    assert drop_conflicting_translations(catalog) == []
    assert len(catalog.translations) == 4


def test_batch_backend_is_used_when_available(tmp_path) -> None:
    """A backend exposing ``translate_batch`` is called once per group."""
    calls: list[list[str]] = []

    class BatchBackend:
        batch_size = 2

        def __call__(self, text: str) -> str:  # pragma: no cover - fallback path
            calls.append([text])
            return "译:" + text

        def translate_batch(self, texts):
            calls.append(list(texts))
            return ["译:" + t for t in texts]

    catalog = TranslationCatalog(tmp_path / "zh.json")
    added = fill_catalog(
        catalog, ["a", "b", "c"], BatchBackend(), delay=0, log=lambda _m: None
    )

    assert added == 3
    assert len(calls) == 2  # 2 + 1, not 3 single calls
    assert catalog.translations == {"a": "译:a", "b": "译:b", "c": "译:c"}


def test_fill_catalog_translates_and_persists(tmp_path) -> None:
    """Missing strings are translated once and written to disk."""
    path = tmp_path / "zh.json"
    catalog = TranslationCatalog(path)
    catalog.translations["Delete"] = "\u5df2\u6709"

    added = fill_catalog(
        catalog,
        ["Delete", "Cancel"],
        fake_backend,
        delay=0,
        log=lambda _msg: None,
    )

    assert added == 1  # only "Cancel" was missing
    assert catalog.translations["Cancel"] == "\u8bd1:Cancel"
    assert catalog.translations["Delete"] == "\u5df2\u6709"  # untouched
    assert TranslationCatalog(path).load().translations["Cancel"] == "\u8bd1:Cancel"


def test_fill_catalog_respects_the_limit(tmp_path) -> None:
    catalog = TranslationCatalog(tmp_path / "zh.json")
    added = fill_catalog(
        catalog, ["a", "b", "c"], fake_backend, delay=0, limit=2, log=lambda _m: None
    )
    assert added == 2
    assert len(catalog.translations) == 2


def test_fill_catalog_skips_failures_instead_of_aborting(tmp_path) -> None:
    """One failing string must not lose the ones that did translate."""
    def flaky(text: str) -> str:
        if text == "b":
            raise RuntimeError("service unavailable")
        return "译:" + text

    catalog = TranslationCatalog(tmp_path / "zh.json")
    added = fill_catalog(
        catalog, ["a", "b", "c"], flaky, delay=0, retries=1, log=lambda _m: None
    )

    assert added == 2
    assert "a" in catalog.translations and "c" in catalog.translations
    assert "b" not in catalog.translations


def test_source_language_needs_no_catalog() -> None:
    """`en` is the authored language: nothing to collect or translate."""
    assert DEFAULT_LANGUAGE == "en"


@pytest.mark.parametrize("backend", ["nope", ""])
def test_unknown_backend_is_rejected(backend: str) -> None:
    from ktem.utils.i18n import make_backend

    with pytest.raises(ValueError):
        make_backend(backend, "zh")


# --------------------------------------------------------------------------- #
# structural safety of a machine translation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("source", "translated", "expected"),
    (
        # a normal translation is accepted
        ("Delete", "\u5220\u9664", "\u5220\u9664"),
        # leaked markup artifacts are stripped
        ("Spec description", '<g id="1">\u89c4\u683c</g>', "\u89c4\u683c"),
        # quotes added by the service are removed
        ("Delete", '"\u5220\u9664"', "\u5220\u9664"),
    ),
)
def test_clean_translation_accepts_usable_output(
    source: str, translated: str, expected: str
) -> None:
    from ktem.utils.i18n import clean_translation

    assert clean_translation(source, translated) == expected


@pytest.mark.parametrize(
    ("source", "translated"),
    (
        # untranslated
        ("Delete", "Delete"),
        ("Delete", ""),
        ("Delete", "   "),
        # a heading must not lose its marker, otherwise "#" renders literally
        ("## Conversations", "\u5bf9\u8bdd"),
        # bold markers must not degrade into "* *"
        ("**Simple QA**: a pipeline.", "* *\u7b80\u5355\u95ee\u7b54* * \uff1a\u4e00\u4e2a\u6d41\u6c34\u7ebf"),
        # list items must keep their bullet
        ("- Supported file types", "\u652f\u6301\u7684\u6587\u4ef6\u7c7b\u578b"),
    ),
)
def test_clean_translation_rejects_damaged_output(source: str, translated: str) -> None:
    """Damaged results are dropped so the English source is kept instead."""
    from ktem.utils.i18n import clean_translation

    assert clean_translation(source, translated) is None


def test_clean_translation_keeps_a_valid_heading() -> None:
    from ktem.utils.i18n import clean_translation

    assert clean_translation("## Conversations", "## \u5bf9\u8bdd") == "## \u5bf9\u8bdd"
    assert (
        clean_translation("- Supported file types", "- \u652f\u6301\u7684\u6587\u4ef6\u7c7b\u578b")
        == "- \u652f\u6301\u7684\u6587\u4ef6\u7c7b\u578b"
    )


def test_clean_translation_rejects_a_lost_placeholder() -> None:
    """A template whose placeholder disappeared can no longer be filled."""
    from ktem.utils.i18n import clean_translation

    assert clean_translation("a {} b", "甲 {} 乙") == "甲 {} 乙"
    assert clean_translation("a {} b", "甲乙") is None


# --------------------------------------------------------------------------- #
# runtime strings: assembled after the components are built
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _reset_runtime_translation():
    yield
    from ktem.utils import i18n

    i18n.configure(DEFAULT_LANGUAGE)


@pytest.fixture
def runtime_catalog(tmp_path):
    """Activate a small catalog for the runtime helpers."""
    from ktem.utils import i18n

    path = tmp_path / "zh.json"
    path.write_text(
        json.dumps(
            {
                "Indexing completed.": "索引完成。",
                'Index "{}" created successfully. Please restart the app!': (
                    '索引 "{}" 创建成功。请重启应用！'
                ),
                "Failed to create LLM '{}': {}": "创建 LLM '{}' 失败：{}",
                "Relevance score": "相关度评分",
                "{} from ": "{} 来自 ",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    catalog = i18n.TranslationCatalog(path).load()
    i18n.configure("zh", catalog)
    return catalog


def test_collect_source_strings_finds_runtime_labels(tmp_path) -> None:
    """Strings only produced at runtime are extracted from the source."""
    from ktem.utils.i18n import collect_source_strings

    package = tmp_path / "pkg"
    (package / "assets" / "js").mkdir(parents=True)
    (package / "mod.py").write_text(
        "tr('Relevance score')\n"
        "gr.Info('Indexing completed.')\n"
        "gr.Warning(f'File {name} has been deleted')\n"
        "gr.Error(str(error))\n"
        "manager.info('not a display string')\n",
        encoding="utf-8",
    )
    (package / "assets" / "js" / "main.js").write_text(
        'node.innerHTML = window.__KTEM_t("version:") + " 1.0";\n',
        encoding="utf-8",
    )

    strings = collect_source_strings(package)

    assert "Relevance score" in strings
    assert "Indexing completed." in strings
    # an f-string becomes a template, so it can be filled at runtime
    assert "File {} has been deleted" in strings
    # a string built in the browser
    assert "version:" in strings
    # not display strings
    assert "not a display string" not in strings


def test_translate_message_uses_an_exact_entry(runtime_catalog) -> None:
    from ktem.utils.i18n import translate_message

    assert translate_message("Indexing completed.") == "索引完成。"


def test_translate_message_fills_a_template(runtime_catalog) -> None:
    from ktem.utils.i18n import translate_message

    assert (
        translate_message('Index "docs" created successfully. Please restart the app!')
        == '索引 "docs" 创建成功。请重启应用！'
    )
    assert (
        translate_message("Failed to create LLM 'deepseek': boom")
        == "创建 LLM 'deepseek' 失败：boom"
    )


def test_translate_message_leaves_unknown_messages_alone(runtime_catalog) -> None:
    from ktem.utils.i18n import translate_message

    assert translate_message("Connection reset by peer") == "Connection reset by peer"


def test_tr_is_identity_without_an_active_catalog() -> None:
    """Wrapping a literal in ``tr`` is always safe, even with no catalog."""
    from ktem.utils import i18n

    i18n.configure(DEFAULT_LANGUAGE)
    assert i18n.tr("Relevance score") == "Relevance score"


def test_tr_returns_the_translation_when_active(runtime_catalog) -> None:
    from ktem.utils import i18n

    assert i18n.tr("Relevance score") == "相关度评分"
    assert i18n.tr("{} from ").format(i18n.tr("Image")) == "Image 来自 "


def test_install_hooks_is_a_no_op_without_a_catalog() -> None:
    import gradio as gr

    from ktem.utils import i18n

    i18n.configure(DEFAULT_LANGUAGE)
    before = gr.Info
    i18n.install_hooks()
    assert gr.Info is before


def test_install_hooks_translates_toasts(runtime_catalog) -> None:
    """One hook covers every ``gr.Info`` / ``gr.Warning`` of the application."""
    import gradio as gr
    from gradio import exceptions as gr_exceptions

    from ktem.utils import i18n

    modules = [gr] + ([gr.helpers] if hasattr(gr, "helpers") else [])
    saved = {
        (id(module), name): (module, name, getattr(module, name))
        for module in modules
        for name in ("Info", "Warning")
        if hasattr(module, name)
    }
    original_error_init = gr_exceptions.Error.__init__

    seen: list[str] = []
    for module in modules:
        for name in ("Info", "Warning"):
            if hasattr(module, name):
                setattr(
                    module,
                    name,
                    lambda message="", *a, _n=name, **k: seen.append(message),
                )
    gr._ktem_i18n_hooked = False

    try:
        i18n.install_hooks()
        gr.Info("Indexing completed.")
        gr.Warning("Failed to create LLM 'x': boom")
    finally:
        for module, name, value in saved.values():
            setattr(module, name, value)
        gr_exceptions.Error.__init__ = original_error_init
        gr._ktem_i18n_hooked = False

    assert seen == ["索引完成。", "创建 LLM 'x' 失败：boom"]


def test_bootstrap_js_publishes_the_catalog(runtime_catalog) -> None:
    from ktem.utils import i18n

    script = i18n.bootstrap_js("zh")
    assert "window.__KTEM_t" in script
    assert "索引完成。" in script


def test_bootstrap_js_without_translations_is_still_defined() -> None:
    """main.js calls the lookup unconditionally, so it must always exist."""
    from ktem.utils import i18n

    i18n.configure(DEFAULT_LANGUAGE)
    script = i18n.bootstrap_js(DEFAULT_LANGUAGE)
    assert "window.__KTEM_t" in script
    assert "window.__KTEM_I18N = {}" in script


def test_bootstrap_js_cannot_close_the_script_tag(tmp_path) -> None:
    """The script is injected inside <script>, so "</script" must be escaped.

    A translation containing it would otherwise terminate the tag early and take
    the whole page down — the same failure mode as a syntax error in the bundle.
    """
    from ktem.utils import i18n

    path = tmp_path / "zh.json"
    path.write_text(
        json.dumps({"Evil": "</script><b>x</b>"}, ensure_ascii=False), encoding="utf-8"
    )
    i18n.configure("zh", i18n.TranslationCatalog(path).load())

    script = i18n.bootstrap_js("zh")

    assert "</script" not in script.lower()
    assert "<\\/script" in script


# --------------------------------------------------------------------------- #
# bundled catalog: a fresh clone is localized without network access
# --------------------------------------------------------------------------- #
def write_catalog(path, entries):
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def catalog_paths(tmp_path, monkeypatch):
    """Point the bundled and user catalog at temporary files."""
    from ktem.utils import i18n

    bundled = tmp_path / "assets" / "i18n" / "zh.json"
    user = tmp_path / "app_data" / "i18n" / "zh.json"
    monkeypatch.setattr(i18n, "bundled_catalog_path", lambda language: bundled)
    monkeypatch.setattr(i18n, "default_catalog_path", lambda language: user)
    return bundled, user


def test_load_catalog_merges_bundled_and_user(catalog_paths) -> None:
    from ktem.utils import i18n

    bundled, user = catalog_paths
    bundled.parent.mkdir(parents=True)
    user.parent.mkdir(parents=True)
    write_catalog(bundled, {"Delete": "删除", "Save": "保存"})
    write_catalog(user, {"Delete": "移除", "Only": "唯一"})

    catalog = i18n.load_catalog("zh")

    assert catalog.lookup("Save") == "保存"  # comes from the repository
    assert catalog.lookup("Delete") == "移除"  # the user entry wins
    assert catalog.lookup("Only") == "唯一"  # user-only entry
    # saving must still target the user catalog, never the repository
    assert catalog.path == user


def test_load_catalog_tolerates_a_missing_bundled_file(catalog_paths) -> None:
    from ktem.utils import i18n

    _, user = catalog_paths
    user.parent.mkdir(parents=True)
    write_catalog(user, {"Only": "唯一"})

    catalog = i18n.load_catalog("zh")

    assert catalog.lookup("Only") == "唯一"
    assert catalog.lookup("Unknown") == "Unknown"


def test_bundle_catalog_writes_the_repository_file(catalog_paths) -> None:
    from ktem.utils import i18n

    bundled, user = catalog_paths
    user.parent.mkdir(parents=True)
    write_catalog(user, {"A": "甲", "B": "乙"})

    source, target, count = i18n.bundle_catalog("zh")

    assert count == 2
    assert source == user
    assert target == bundled
    assert json.loads(bundled.read_text(encoding="utf-8")) == {"A": "甲", "B": "乙"}
