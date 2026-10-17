"""UI localization backed by an online translation service.

Translations are **not** hard-coded. Display strings are collected from the built
Gradio UI, translated through the :mod:`deep_translator` library, and persisted to
a JSON catalog that every later run reuses — so the app boots instantly and
offline once the catalog exists.

Safety model (unchanged from the previous approach, and the reason this is safe):

* only attributes that are *rendered as text* are rewritten (labels, hints,
  placeholders, button captions, markdown/html bodies, table headers, choices);
* component ``value`` fields that the application logic matches on are never
  touched — for input components they hold real data (prompt templates, specs);
* choice lists are translated as ``(label, value)`` pairs so the value the
  backend receives is always preserved.

Building the catalog is an explicit step (see :func:`build_catalog` and the
``python -m ktem.utils.i18n build`` entry point) because a free translation
service needs roughly two seconds per string.
"""

from __future__ import annotations

import json
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

#: Language the UI is authored in; selecting it disables localization entirely.
DEFAULT_LANGUAGE = "en"

#: Translation backends. ``mymemory`` / ``google`` / ``libre`` come from the
#: ``deep-translator`` library; ``llm`` reuses the chat model already configured
#: for the app (no extra credential) and preserves Markdown structure, which the
#: free services were measured to damage.
BACKENDS = ("mymemory", "google", "libre", "llm")

#: Instruction handed to the LLM backend. It must return the translation only.
LLM_SYSTEM_PROMPT = (
    "You translate user-interface strings of a document question-answering app "
    "from English into {language}.\n"
    "You receive a JSON array of strings. Reply with a JSON array of the SAME "
    "length, each element being the translation of the element at the same index.\n"
    "Rules:\n"
    "1. Reply with the JSON array only. No prose, no code fences, no explanations.\n"
    "2. Preserve Markdown/HTML structure exactly: keep leading #, ##, ###, "
    "list markers (- ), bold markers **...**, <mark>...</mark> and {{placeholders}}. "
    "A string containing {{}} is a template: keep every {{}} in the same order.\n"
    "3. Keep product names, model names, acronyms (LLM, MCP, RAG, ReAct, ReWOO, "
    "API, JSON, YAML, URL) and code identifiers unchanged.\n"
    "4. Use concise, natural UI wording of a few characters when the source is short.\n"
    "5. Each element is an independent UI label: translate it on its own. A language "
    "name must stay a language name (e.g. names in a language selector must remain "
    "distinguishable from one another), and never replace a label with its own "
    "category or with the target language's name."
)

#: Artifacts some free services leak into their responses (e.g. Google's `<g>`).
_TAG_ARTIFACT = re.compile(r"</?[a-zA-Z][^>]*>")

#: Longest string worth sending: free services reject or mangle longer payloads.
#: The long-form Help documents are localized as files instead (docs/*.zh.md).
MAX_STRING_LENGTH = 500

#: Dynamic labels built at runtime, so they are not found by walking components.
#: ``Version:`` and ``Changelogs`` are assembled by the Help page; the last three
#: are document types shown by the reference header (``render.py``). They come
#: from document metadata, so no literal exists for the source scan to find.
EXTRA_STRINGS = (
    "Version:",
    "Changelogs",
    "Image",
    "Table",
    "Text",
    "Thumbnail",
)

#: Attributes rendered as plain text, keyed by Gradio component class name.
#: ``value`` is listed only for components whose value *is* the caption/content.
_DISPLAY_ATTRS: dict[str, tuple[str, ...]] = {
    "Accordion": ("label",),
    "Audio": ("label",),
    "Button": ("value",),
    "Chatbot": ("label", "placeholder"),
    "Checkbox": ("label", "info"),
    "CheckboxGroup": ("label", "info", "choices"),
    "Code": ("label",),
    "ColorPicker": ("label",),
    "Dataframe": ("headers",),
    "Dataset": ("label", "headers"),
    "DownloadButton": ("label",),
    "Dropdown": ("label", "info", "choices"),
    "File": ("label",),
    "HTML": ("value",),
    "Image": ("label",),
    "JSON": ("label",),
    "Markdown": ("value",),
    "Model3D": ("label",),
    "MultimodalTextbox": ("label", "placeholder"),
    "Number": ("label", "info"),
    "Radio": ("label", "info", "choices"),
    "Slider": ("label", "info"),
    "Tab": ("label",),
    "Textbox": ("label", "info", "placeholder"),
    "UploadButton": ("label",),
    "Video": ("label",),
}

_TEXT_LIST_ATTRS = frozenset({"headers"})

#: Language code -> the locale expected by the translation services.
_LOCALE = {"zh": "zh-CN", "zh-cn": "zh-CN", "en": "en-US"}


# --------------------------------------------------------------------------- #
# collecting and applying
# --------------------------------------------------------------------------- #
def _iter_strings(block: Any) -> Iterable[str]:
    for attr in _DISPLAY_ATTRS.get(type(block).__name__, ()):
        try:
            value = getattr(block, attr, None)
        except AttributeError:
            continue

        if attr == "choices":
            if not isinstance(value, (list, tuple)):
                continue
            for item in value:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    if isinstance(item[0], str):
                        yield item[0]
                elif isinstance(item, str):
                    yield item
            continue

        if attr in _TEXT_LIST_ATTRS:
            if isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, str):
                        yield item
            continue

        if isinstance(value, str):
            yield value


def collect_display_strings(
    blocks: Mapping[Any, Any], extra: Iterable[str] = ()
) -> list[str]:
    """Return every distinct display string of a built ui, in a stable order.

    Args:
        blocks: the ``gr.Blocks.blocks`` mapping (id -> component).
        extra: further strings to include — use :func:`collect_source_strings`
            so that labels assembled after the build are covered too.

    Returns:
        Sorted unique strings, filtered to those worth sending to a translator.
    """
    found: set[str] = set(EXTRA_STRINGS)
    found.update(extra)
    for block in blocks.values():
        for text in _iter_strings(block):
            found.add(text)

    usable = []
    for text in sorted(found):
        if not text.strip():
            continue
        if len(text) > MAX_STRING_LENGTH:
            continue
        if _has_cjk(text):
            continue  # already localized, nothing to translate
        usable.append(text)
    return usable


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def translate_choices(choices: Any, translations: Mapping[str, str]) -> Any:
    """Translate the label of each choice, preserving every value.

    A bare string doubles as its own value, so it is expanded to a pair; the
    original string stays the value and is what the backend keeps receiving.
    """
    if not isinstance(choices, (list, tuple)):
        return choices

    result: list[Any] = []
    changed = False
    for item in choices:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            label, value = item
            new_label = translations.get(label, label) if isinstance(label, str) else label
            if new_label != label:
                changed = True
            result.append((new_label, value))
        elif isinstance(item, str):
            new_label = translations.get(item, item)
            if new_label != item:
                changed = True
                result.append((new_label, item))
            else:
                result.append(item)
        else:
            result.append(item)

    if not changed:
        return choices
    return tuple(result) if isinstance(choices, tuple) else result


def _apply(block: Any, attr: str, translations: Mapping[str, str]) -> bool:
    if attr == "choices":
        try:
            value = block.choices
        except AttributeError:
            return False
        new_value = translate_choices(value, translations)
        if new_value is value or new_value == value:
            return False
        block.choices = new_value
        return True

    try:
        value = getattr(block, attr, None)
    except AttributeError:
        return False

    if attr in _TEXT_LIST_ATTRS:
        if not isinstance(value, (list, tuple)):
            return False
        new_list = [translations.get(v, v) if isinstance(v, str) else v for v in value]
        if new_list == list(value):
            return False
        setattr(block, attr, new_list)
        return True

    if not isinstance(value, str):
        return False
    new_value = translations.get(value, value)
    if new_value == value:
        return False
    setattr(block, attr, new_value)
    return True


def localize_blocks(blocks: Mapping[Any, Any], translations: Mapping[str, str]) -> int:
    """Rewrite the display strings of every block using ``translations``.

    Args:
        blocks: the ``gr.Blocks.blocks`` mapping (id -> component).
        translations: source string -> translated string.

    Returns:
        How many attributes were rewritten, for logging and verification.
    """
    if not translations:
        return 0
    changed = 0
    for block in blocks.values():
        for attr in _DISPLAY_ATTRS.get(type(block).__name__, ()):
            if _apply(block, attr, translations):
                changed += 1
    return changed


# --------------------------------------------------------------------------- #
# catalog (the on-disk cache of translations)
# --------------------------------------------------------------------------- #
class TranslationCatalog:
    """A JSON map of source string -> translation, persisted between runs."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.translations: dict[str, str] = {}

    def load(self) -> "TranslationCatalog":
        if self.path.exists():
            with self.path.open(encoding="utf-8") as fi:
                data = json.load(fi)
            if isinstance(data, dict):
                self.translations = {
                    str(k): str(v) for k, v in data.items() if isinstance(v, str)
                }
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fo:
            json.dump(self.translations, fo, ensure_ascii=False, indent=2, sort_keys=True)
            fo.write("\n")

    def missing(self, strings: Sequence[str]) -> list[str]:
        return [s for s in strings if s not in self.translations]

    def lookup(self, text: str) -> str:
        return self.translations.get(text, text)


# --------------------------------------------------------------------------- #
# translation providers
# --------------------------------------------------------------------------- #
TranslateFn = Callable[[str], str]


def clean_translation(source: str, translated: str) -> str | None:
    """Return a usable translation of ``source``, or ``None`` to keep the source.

    Free machine-translation services occasionally return markup artifacts or
    drop the Markdown structure of the string (headings, bullet or bold markers),
    which would render as literal characters in the UI. Rather than displaying a
    damaged string, such results are rejected and the English source is kept.

    Args:
        source: the original English string.
        translated: what the service returned.

    Returns:
        The cleaned translation, or ``None`` when it is not safe to use.
    """
    if not isinstance(translated, str):
        return None

    text = _TAG_ARTIFACT.sub("", translated).strip()
    text = text.strip('"').strip()
    if not text:
        return None
    if text == source:
        return None  # nothing was translated

    # a heading must stay a heading, otherwise it renders as literal "#"
    source_hashes = len(source) - len(source.lstrip("#"))
    text_hashes = len(text) - len(text.lstrip("#"))
    if source_hashes and not text_hashes:
        return None

    # bold / italic markers must survive intact, not turn into "* *"
    if source.count("**") and text.count("**") != source.count("**"):
        return None

    # list items must keep their bullet
    stripped_source = source.lstrip()
    stripped_text = text.lstrip()
    if stripped_source[:2] in ("- ", "* ") and stripped_text[:2] not in ("- ", "* "):
        return None

    # a template must keep its placeholders, or it can no longer be filled
    if source.count("{}") and text.count("{}") != source.count("{}"):
        return None

    return text


class _LLMBackend:
    """Translates through the chat model, batching strings for context.

    Batching is not only faster: translating a whole group at once gives the model
    the surrounding context, which matters for lists such as language selectors
    where a context-free translation would collapse ``English`` and ``Chinese``
    into the same word.
    """

    def __init__(self, language: str, batch_size: int = 20) -> None:
        from decouple import config
        from openai import OpenAI

        api_key = config("DEEPSEEK_API_KEY", default="") or config(
            "OPENAI_API_KEY", default=""
        )
        if not api_key or api_key.upper().startswith("SK-REPLACE"):
            raise RuntimeError(
                "the 'llm' translation backend needs DEEPSEEK_API_KEY or "
                "OPENAI_API_KEY to be configured"
            )

        self._client = OpenAI(
            api_key=api_key,
            base_url=config("DEEPSEEK_API_BASE", default="") or None,
            timeout=120,
        )
        self._model = config("DEEPSEEK_CHAT_MODEL", default="") or config(
            "OPENAI_CHAT_MODEL", default="gpt-4o-mini"
        )
        self._system_prompt = LLM_SYSTEM_PROMPT.format(language=language)
        self.batch_size = batch_size

    def _ask(self, texts: Sequence[str]) -> list[str]:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": json.dumps(list(texts), ensure_ascii=False)},
            ],
        )
        content = (response.choices[0].message.content or "").strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content).strip()
        data = json.loads(content)
        if not isinstance(data, list) or len(data) != len(texts):
            raise ValueError(
                "expected %d translations, got %r" % (len(texts), type(data).__name__)
            )
        return [str(item) for item in data]

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        return self._ask(texts)

    def __call__(self, text: str) -> str:
        return self._ask([text])[0]


def make_llm_backend(language: str) -> TranslateFn:
    """Translate through the chat model the application is already configured with.

    Reads the same environment keys as ``flowsettings`` so no extra credential is
    needed. Unlike the free services this keeps Markdown structure, uses
    consistent terminology, and can be batched.

    Args:
        language: target language code, e.g. ``zh``.

    Returns:
        A callable translating a single string, exposing ``translate_batch`` too.

    Raises:
        RuntimeError: when no API key is configured.
    """
    return _LLMBackend(language)


def make_backend(backend: str, language: str) -> TranslateFn:
    """Build a ``text -> translation`` callable for the given backend.

    Args:
        backend: one of :data:`BACKENDS`.
        language: target language code, e.g. ``zh``.

    Returns:
        A callable translating a single string.

    Raises:
        ValueError: for an unknown backend.
        ImportError: when ``deep-translator`` is not installed.
    """
    if backend == "llm":
        return make_llm_backend(language)

    target = _LOCALE.get(language.lower(), language)

    if backend == "google":
        from deep_translator import GoogleTranslator

        instance = GoogleTranslator(source="en", target=target)
    elif backend == "mymemory":
        from deep_translator import MyMemoryTranslator

        instance = MyMemoryTranslator(source="en-US", target=target)
    elif backend == "libre":
        from deep_translator import LibreTranslate

        instance = LibreTranslate(source="en", target=target)
    else:
        raise ValueError(
            "unknown translation backend %r, expected one of %s" % (backend, BACKENDS)
        )

    return instance.translate


def _translate_one(
    text: str,
    backend: TranslateFn,
    *,
    delay: float,
    retries: int,
) -> tuple[str, str | None]:
    """Translate one string, retrying with backoff. Never raises.

    A structurally damaged result is not retried (the service would answer the
    same way); it simply keeps the English source.
    """
    for attempt in range(retries):
        try:
            if delay:
                time.sleep(delay)
            return text, clean_translation(text, backend(text))
        except Exception:  # noqa: BLE001 - a bad string must not kill the build
            if attempt == retries - 1:
                return text, None
            time.sleep(delay * (attempt + 2))
    return text, None


def fill_catalog(
    catalog: TranslationCatalog,
    strings: Sequence[str],
    backend: TranslateFn,
    *,
    delay: float = 0.35,
    retries: int = 3,
    limit: int | None = None,
    workers: int = 1,
    timeout: float = 20.0,
    log: Callable[[str], None] | None = None,
) -> int:
    """Translate the strings missing from ``catalog`` and persist the result.

    Two practical problems of the free services are handled explicitly:

    * ``deep-translator`` issues requests **without a timeout**, so a stalled
      connection would hang the build forever — ``socket.setdefaulttimeout`` is
      applied for the duration of the call;
    * a single bad string must not lose the rest, so failures are retried with a
      growing backoff and then skipped, and the catalog is flushed periodically.

    Args:
        catalog: the catalog to extend and save.
        strings: candidate source strings.
        backend: callable returned by :func:`make_backend`.
        delay: seconds to wait before each request.
        retries: attempts per string before giving up.
        limit: stop after this many strings (useful for a smoke test).
        workers: concurrent requests; 1 means sequential.
        timeout: per-request socket timeout in seconds.
        log: progress callback; defaults to :func:`print`.

    Returns:
        How many strings were translated and stored.
    """
    log = log or print
    todo = catalog.missing(strings)
    if limit is not None:
        todo = todo[:limit]
    if not todo:
        return 0

    added = 0
    done = 0
    batch_fn = getattr(backend, "translate_batch", None)
    batch_size = max(1, int(getattr(backend, "batch_size", 20) or 20))
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        if batch_fn is not None and len(todo) > 1:
            for start in range(0, len(todo), batch_size):
                group = todo[start : start + batch_size]
                try:
                    results = batch_fn(group)
                except Exception as exc:  # noqa: BLE001 - fall back to one by one
                    log(
                        "  [batch failed] %s: %s"
                        % (type(exc).__name__, str(exc)[:120])
                    )
                    for text in group:
                        text, translated = _translate_one(
                            text, backend, delay=delay, retries=retries
                        )
                        done += 1
                        if translated:
                            catalog.translations[text] = translated
                            added += 1
                        else:
                            log("  [skip] %r" % (text[:50],))
                    catalog.save()
                    continue

                for text, translated in zip(group, results):
                    done += 1
                    cleaned = clean_translation(text, translated)
                    if cleaned:
                        catalog.translations[text] = cleaned
                        added += 1
                    else:
                        log("  [skip] %r" % (text[:50],))
                catalog.save()
                log("  %d/%d processed (%d new)" % (done, len(todo), added))
        elif workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [
                    pool.submit(
                        _translate_one, text, backend, delay=delay, retries=retries
                    )
                    for text in todo
                ]
                for future in as_completed(futures):
                    text, translated = future.result()
                    done += 1
                    if translated:
                        catalog.translations[text] = translated
                        added += 1
                    else:
                        log("  [skip] %r" % (text[:50],))
                    if done % 20 == 0:
                        catalog.save()
                        log("  %d/%d processed (%d new)" % (done, len(todo), added))
        else:
            for text in todo:
                text, translated = _translate_one(
                    text, backend, delay=delay, retries=retries
                )
                done += 1
                if translated:
                    catalog.translations[text] = translated
                    added += 1
                else:
                    log("  [skip] %r" % (text[:50],))
                if done % 20 == 0:
                    catalog.save()
                    log("  %d/%d processed (%d new)" % (done, len(todo), added))
    finally:
        socket.setdefaulttimeout(previous_timeout)
        catalog.save()

    return added


def default_catalog_path(language: str) -> Path:
    """Where the catalog for ``language`` lives (inside the app data directory)."""
    from theflow.settings import settings

    app_data = Path(str(getattr(settings, "KH_APP_DATA_DIR", ".")))
    return app_data / "i18n" / ("%s.json" % language)


def bundled_catalog_path(language: str) -> Path:
    """Catalog committed to the repository, so a fresh clone is already localized.

    The file is *generated* (see :func:`build_catalog` / :func:`bundle_catalog`),
    not hand-written: it is the cache produced by the translation backend, kept
    under version control so the app does not have to reach the network — or need
    a configured model — before it can render its own interface.
    """
    package_dir = Path(__file__).resolve().parents[1]
    return package_dir / "assets" / "i18n" / ("%s.json" % language)


def load_catalog(language: str) -> TranslationCatalog:
    """Load the bundled catalog, then overlay the user's catalog on top.

    The user catalog wins entry by entry, so an individual label can be fixed in
    ``ktem_app_data/i18n/<lang>.json`` without touching the repository, while
    everything else still comes from the shipped file.
    """
    catalog = TranslationCatalog(default_catalog_path(language))
    for path in (bundled_catalog_path(language), catalog.path):
        if not path.exists():
            continue
        catalog.translations.update(TranslationCatalog(path).load().translations)
    return catalog


def bundle_catalog(language: str) -> tuple[Path, Path, int]:
    """Copy the user catalog into the repository so a fresh clone is localized.

    Args:
        language: target language code, e.g. ``zh``.

    Returns:
        ``(source_path, bundled_path, entry_count)``.
    """
    source = TranslationCatalog(default_catalog_path(language)).load()
    target = bundled_catalog_path(language)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(source.translations, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return source.path, target, len(source.translations)


_LOOKUP: dict[str, TranslationCatalog] = {}


def lookup(text: str, language: str) -> str:
    """Translate ``text`` from the on-disk catalog; never touches the network.

    Used for labels assembled at runtime, which the component walk cannot see.
    """
    if language == DEFAULT_LANGUAGE:
        return text
    catalog = _LOOKUP.get(language)
    if catalog is None:
        catalog = load_catalog(language)
        _LOOKUP[language] = catalog
    return catalog.lookup(text)


def normalize_label(text: str) -> str:
    """Reduce a UI label to a form that ignores case and plural spelling.

    Used to decide whether two source strings are really the same label, so that
    ``Admin``/``admin`` and ``Vendors``/``vendor`` are not mistaken for a
    translation conflict.
    """
    normalized = " ".join(text.split()).lower()
    if normalized.endswith("s") and not normalized.endswith("ss"):
        normalized = normalized[:-1]
    return normalized


def drop_conflicting_translations(catalog: TranslationCatalog) -> list[str]:
    """Remove entries whose translation is shared by a different source string.

    Context-free translation collapses similar labels into the same word — for
    example a language selector where both ``English`` and ``Chinese`` come back
    as ``中文``. A collision means at least one of them is wrong, and showing two
    identical entries is worse than showing the original English, so such entries
    are dropped.

    Args:
        catalog: the catalog to clean in place.

    Returns:
        The source strings that were dropped.
    """
    by_target: dict[str, list[str]] = {}
    for source, target in catalog.translations.items():
        by_target.setdefault(target, []).append(source)

    dropped: list[str] = []
    for sources in by_target.values():
        # Labels that only differ in case, surrounding spaces or plural form
        # ("Admin" vs "admin", "Vendors" vs "vendor") are the same label and
        # legitimately share a translation; only genuinely different labels
        # mapping to one target are a conflict.
        if len({normalize_label(source) for source in sources}) > 1:
            for source in sources:
                catalog.translations.pop(source, None)
                dropped.append(source)
    return dropped


def build_catalog(
    language: str,
    backend: str,
    *,
    limit: int | None = None,
    workers: int = 4,
    log: Callable[[str], None] | None = None,
) -> tuple[int, int]:
    """Collect the UI strings, translate the missing ones, and save the catalog.

    Args:
        language: target language code, e.g. ``zh``.
        backend: one of :data:`BACKENDS`.
        limit: stop after this many strings (handy for a smoke test).
        workers: concurrent translation requests.
        log: progress callback.

    Returns:
        ``(total_strings, newly_translated)``.
    """
    from ktem.main import App  # imported lazily: pulls in the whole application

    log = log or print
    app = App()
    demo = app.make()
    strings = collect_display_strings(demo.blocks, collect_source_strings())
    log("collected %d display strings" % len(strings))

    catalog = load_catalog(language)
    log("catalog %s holds %d entries" % (catalog.path, len(catalog.translations)))

    added = fill_catalog(
        catalog,
        strings,
        make_backend(backend, language),
        limit=limit,
        workers=workers,
        log=log,
    )

    dropped = drop_conflicting_translations(catalog)
    if dropped:
        log("dropped %d ambiguous entries: %s" % (len(dropped), ", ".join(dropped[:8])))
        catalog.save()

    log("translated %d new strings via %s" % (added, backend))
    return len(strings), added


# --------------------------------------------------------------------------- #
# runtime translation: strings assembled *after* the components are built
# --------------------------------------------------------------------------- #
# Nothing below runs during the component walk, so these strings never appear in
# the block tree: reference headers built while rendering an answer, toasts
# raised from event callbacks, and literals the browser assembles itself.
_RUNTIME: dict[str, Any] = {"language": DEFAULT_LANGUAGE, "catalog": None}

#: Compiled template matchers, rebuilt whenever the active catalog changes.
_PATTERNS: list[tuple[Any, str]] = []

#: Calls whose first argument is displayed to the user by Gradio.
_TOAST_FUNCS = frozenset({"Info", "Warning", "Error", "Success"})

#: Browser-side lookups in the JavaScript assets: ``__KTEM_t("literal")``.
_JS_LOOKUP = re.compile(r"""__KTEM_t\(\s*["']([^"'\n]+)["']\s*\)""")


def configure(language: str, catalog: TranslationCatalog | None = None) -> None:
    """Activate ``language`` for runtime translation.

    Must run before the UI is built, so that everything assembled later (toasts,
    reference headers, the JS bootstrap) uses the same catalog as the walk.

    Args:
        language: target language code; the authored language disables it.
        catalog: an already-loaded catalog, to avoid reading the file twice.
    """
    _RUNTIME["language"] = language or DEFAULT_LANGUAGE
    if _RUNTIME["language"] == DEFAULT_LANGUAGE:
        _RUNTIME["catalog"] = None
    else:
        _RUNTIME["catalog"] = catalog or load_catalog(_RUNTIME["language"])
    _PATTERNS.clear()


def tr(text: str) -> str:
    """Translate a display string that is assembled at runtime.

    Returns ``text`` unchanged when localization is off or the catalog has no
    entry, which makes this safe to wrap around any user-visible literal.
    """
    catalog = _RUNTIME["catalog"]
    if catalog is None or not isinstance(text, str) or not text:
        return text
    return catalog.lookup(text)


def _template_patterns() -> list[tuple[Any, str]]:
    """Templates in the catalog, compiled and ordered most-specific first.

    A message built with an f-string (``f"File {name} has been deleted"``) is
    collected as the template ``"File {} has been deleted"``. Matching the
    rendered text against those templates is what lets such messages be
    translated without rewriting every call site.
    """
    catalog = _RUNTIME["catalog"]
    if catalog is None:
        return []
    if not _PATTERNS:
        for source, target in catalog.translations.items():
            if "{}" not in source or "{}" not in target:
                continue
            body = "(.+?)".join(re.escape(part) for part in source.split("{}"))
            try:
                pattern = re.compile(r"\A" + body + r"\Z", re.DOTALL)
            except re.error:  # pragma: no cover - escape() cannot produce this
                continue
            _PATTERNS.append((pattern, target))
        # most literal text first, so "File {} has been deleted" wins over "File {}"
        _PATTERNS.sort(key=lambda item: -len(item[0].pattern))
    return _PATTERNS


def translate_message(message: str) -> str:
    """Translate a runtime message, filling in what was interpolated.

    Falls back to the original message, so an unknown or ambiguous message is
    shown in English rather than mangled.
    """
    catalog = _RUNTIME["catalog"]
    if catalog is None or not isinstance(message, str) or not message:
        return message

    direct = catalog.translations.get(message)
    if direct is not None:
        return direct

    for pattern, target in _template_patterns():
        match = pattern.match(message)
        if not match:
            continue
        values = match.groups()
        if target.count("{}") != len(values):
            continue
        try:
            return target.format(*values)
        except (IndexError, KeyError, ValueError):
            continue
    return message


def install_hooks() -> None:
    """Route Gradio notifications through the catalog.

    Every toast of the application goes through ``gr.Info``, ``gr.Warning`` or
    ``raise gr.Error``, so translating at those three entry points localizes all
    of them without editing dozens of call sites. ``Error`` is a class used in
    ``except`` clauses, so its ``__init__`` is patched rather than replacing it
    (a replacement function would break ``except gr.Error``).
    """
    if _RUNTIME["catalog"] is None:
        return

    import gradio as gr
    from gradio import exceptions as gr_exceptions

    if getattr(gr, "_ktem_i18n_hooked", False):
        return

    def make_wrapper(original: Callable) -> Callable:
        def wrapper(message: str = "", *args: Any, **kwargs: Any) -> Any:
            return original(translate_message(message), *args, **kwargs)

        wrapper.__wrapped__ = original  # type: ignore[attr-defined]
        return wrapper

    for module in (gr, gr.helpers if hasattr(gr, "helpers") else None):
        if module is None:
            continue
        for name in ("Info", "Warning"):
            original = getattr(module, name, None)
            if callable(original):
                setattr(module, name, make_wrapper(original))

    error_init = gr_exceptions.Error.__init__

    def patched_init(self, message="", *args, **kwargs):
        error_init(self, translate_message(message), *args, **kwargs)

    gr_exceptions.Error.__init__ = patched_init  # type: ignore[method-assign]
    gr._ktem_i18n_hooked = True  # type: ignore[attr-defined]


def bootstrap_js(language: str | None = None) -> str:
    """Return the script that exposes the catalog to the browser.

    ``main.js`` assembles a few strings in the browser (the version tag, the
    conversation placeholder, the "Explain" prefix). They are unreachable from
    Python, so the catalog is published as ``window.__KTEM_I18N`` and read through
    ``__KTEM_t``, which falls back to the source string when a key is missing.

    The result is injected inside a ``<script>`` tag in ``<head>``: it must be
    plain statements, *not* prepended to Gradio's ``js`` argument, which is
    evaluated as one function expression.
    """
    language = language or _RUNTIME["language"]
    catalog = _RUNTIME["catalog"]
    if language == DEFAULT_LANGUAGE:
        payload: dict[str, str] = {}
    else:
        payload = dict((catalog or load_catalog(language)).translations)

    # "</" would close the surrounding <script> tag early if a translation ever
    # contains it; JSON accepts the escaped form and it renders the same.
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")

    # Always defined: main.js calls __KTEM_t unconditionally, and an identity
    # function is what localization off means.
    return (
        "window.__KTEM_I18N = %s;\n"
        "window.__KTEM_t = function (s) {\n"
        "  var t = window.__KTEM_I18N[s];\n"
        "  return t === undefined ? s : t;\n"
        "};\n" % data
    )


def _literal_text(node: Any) -> str | None:
    """Return the text of a ``str`` / f-string node, ``{}`` for each literal part."""
    import ast

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("{}")
        return "".join(parts)
    return None


def collect_source_strings(root: str | Path | None = None) -> list[str]:
    """Find the display strings that the component walk cannot see.

    Two kinds exist: Python strings handed to :func:`tr` or to a Gradio
    notification, and literals the browser looks up (``__KTEM_t("...")`` in the
    JS assets). They are extracted from the source with :mod:`ast` — the gettext
    ``xgettext`` step in miniature — so new call sites are covered automatically
    instead of being listed by hand.

    Args:
        root: the ``ktem`` package directory; defaults to its real location.

    Returns:
        Sorted unique source strings.
    """
    import ast

    root = Path(root) if root else Path(__file__).resolve().parents[1]
    found: set[str] = set()

    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            is_tr = isinstance(func, ast.Name) and func.id == "tr"
            is_toast = (
                isinstance(func, ast.Attribute) and func.attr in _TOAST_FUNCS
            )
            if not (is_tr or is_toast):
                continue
            text = _literal_text(node.args[0])
            if text:
                found.add(text)

    for path in (root / "assets" / "js").glob("*.js"):
        try:
            found.update(_JS_LOOKUP.findall(path.read_text(encoding="utf-8")))
        except OSError:  # pragma: no cover - asset missing in a stripped install
            continue

    return sorted(found)


def _main(argv: Sequence[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m ktem.utils.i18n",
        description="Build the UI translation catalog from an online service.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="translate missing UI strings and save them")
    build.add_argument("--language", default="zh", help="target language (default: zh)")
    build.add_argument(
        "--backend", default="mymemory", choices=BACKENDS, help="translation backend"
    )
    build.add_argument("--limit", type=int, default=None, help="only translate N strings")
    build.add_argument(
        "--workers", type=int, default=4, help="concurrent requests (default: 4)"
    )

    stats = sub.add_parser("stats", help="show what the catalog currently holds")
    stats.add_argument("--language", default="zh", help="target language (default: zh)")

    bundle = sub.add_parser(
        "bundle", help="copy the user catalog into the repository (assets/i18n)"
    )
    bundle.add_argument("--language", default="zh", help="target language (default: zh)")

    args = parser.parse_args(argv)

    if args.command == "stats":
        catalog = load_catalog(args.language)
        print(
            "bundled: %s (%d entries)"
            % (
                bundled_catalog_path(args.language),
                len(
                    TranslationCatalog(bundled_catalog_path(args.language))
                    .load()
                    .translations
                ),
            )
        )
        print("user   : %s" % catalog.path)
        print("merged : %d entries" % len(catalog.translations))
        return 0

    if args.command == "bundle":
        source, target, count = bundle_catalog(args.language)
        print("copied %d entries" % count)
        print("  from %s" % source)
        print("  to   %s" % target)
        return 0

    total, added = build_catalog(
        args.language, args.backend, limit=args.limit, workers=args.workers
    )
    print("done: %d strings, %d newly translated" % (total, added))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    import sys

    raise SystemExit(_main(sys.argv[1:]))


__all__ = [
    "BACKENDS",
    "DEFAULT_LANGUAGE",
    "EXTRA_STRINGS",
    "MAX_STRING_LENGTH",
    "TranslationCatalog",
    "bootstrap_js",
    "bundle_catalog",
    "bundled_catalog_path",
    "build_catalog",
    "clean_translation",
    "collect_display_strings",
    "collect_source_strings",
    "configure",
    "default_catalog_path",
    "drop_conflicting_translations",
    "fill_catalog",
    "install_hooks",
    "load_catalog",
    "localize_blocks",
    "lookup",
    "make_backend",
    "make_llm_backend",
    "tr",
    "translate_choices",
    "translate_message",
]
