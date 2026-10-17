from importlib.metadata import version
from pathlib import Path

import gradio as gr
import requests
from decouple import config
from ktem.utils.i18n import lookup
from theflow.settings import settings

KH_DEMO_MODE = getattr(settings, "KH_DEMO_MODE", False)
KH_UI_LANGUAGE = getattr(settings, "KH_UI_LANGUAGE", "en")
HF_SPACE_URL = config("HF_SPACE_URL", default="")


def read_localized_doc(doc_dir: Path, name: str, language: str) -> str | None:
    """Read ``<name>.<language>.md`` when it exists, else ``<name>.md``.

    Args:
        doc_dir: directory holding the bundled documentation.
        name: document base name, without extension.
        language: current UI language code.

    Returns:
        The document content, or ``None`` when no local file exists (the caller
        then falls back to fetching it from the repository).
    """
    candidates = []
    if language and language != "en":
        candidates.append(doc_dir / f"{name}.{language}.md")
    candidates.append(doc_dir / f"{name}.md")

    for path in candidates:
        if path.exists():
            with path.open(encoding="utf-8") as fi:
                return fi.read()
    return None


def get_remote_doc(url: str) -> str:
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.text
    except Exception as e:
        print(f"Failed to fetch document from {url}: {e}")
        return ""


def download_changelogs(release_url: str) -> str:
    try:
        res = requests.get(release_url).json()
        changelogs = res.get("body", "")

        return changelogs
    except Exception as e:
        print(f"Failed to fetch changelogs from {release_url}: {e}")
        return ""


class HelpPage:
    def __init__(
        self,
        app,
        doc_dir: str = settings.KH_DOC_DIR,
        remote_content_url: str = (
            "https://raw.githubusercontent.com/wangwuqiang2026/citeask"
        ),
        app_version: str | None = settings.KH_APP_VERSION,
        changelogs_cache_dir: str
        | Path = (Path(settings.KH_APP_DATA_DIR) / "changelogs"),
    ):
        self._app = app
        self.doc_dir = Path(doc_dir)
        self.remote_content_url = remote_content_url
        self.app_version = app_version
        self.changelogs_cache_dir = Path(changelogs_cache_dir)

        self.changelogs_cache_dir.mkdir(parents=True, exist_ok=True)

        about_md = read_localized_doc(self.doc_dir, "about", KH_UI_LANGUAGE)
        if about_md is None:  # fetch from remote
            about_md = get_remote_doc(
                f"{self.remote_content_url}/v{self.app_version}/docs/about.md"
            )
        if about_md:
            with gr.Accordion("About"):
                if self.app_version:
                    version_label = lookup("Version:", KH_UI_LANGUAGE)
                    about_md = f"{version_label} {self.app_version}\n\n{about_md}"
                gr.Markdown(about_md)

        if KH_DEMO_MODE:
            with gr.Accordion("Create Your Own Space"):
                gr.Markdown(
                    "This is a demo with limited functionality. "
                    "Use **Create space** button to install the app "
                    "in your own space with all features "
                    "(including upload and manage your private "
                    "documents securely)."
                )
                gr.Button(
                    value="Create Your Own Space",
                    link=HF_SPACE_URL,
                    variant="primary",
                    size="lg",
                )

        user_guide_md = read_localized_doc(self.doc_dir, "usage", KH_UI_LANGUAGE)
        if user_guide_md is None:  # fetch from remote
            user_guide_md = get_remote_doc(
                f"{self.remote_content_url}/v{self.app_version}/docs/usage.md"
            )
        if user_guide_md:
            with gr.Accordion("User Guide", open=not KH_DEMO_MODE):
                gr.Markdown(user_guide_md)

        if self.app_version:
            # try retrieve from cache
            changelogs = ""

            if (self.changelogs_cache_dir / f"{version}.md").exists():
                with open(self.changelogs_cache_dir / f"{version}.md", "r") as fi:
                    changelogs = fi.read()
            else:
                release_url_base = (
                    "https://api.github.com/repos/wangwuqiang2026/citeask/releases"
                )
                changelogs = download_changelogs(
                    release_url=f"{release_url_base}/tags/v{self.app_version}"
                )

                # cache the changelogs
                if not self.changelogs_cache_dir.exists():
                    self.changelogs_cache_dir.mkdir(parents=True, exist_ok=True)
                with open(
                    self.changelogs_cache_dir / f"{self.app_version}.md", "w"
                ) as fi:
                    fi.write(changelogs)

            if changelogs:
                changelog_label = lookup("Changelogs", KH_UI_LANGUAGE)
                with gr.Accordion(f"{changelog_label} (v{self.app_version})"):
                    gr.Markdown(changelogs)
