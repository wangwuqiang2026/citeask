"""The documentation's internal links must resolve (ROADMAP §10).

README, ROADMAP and MODIFICATIONS are the deliverable's own evidence: every claim
points at a section, a file or a line. A renamed page or a typo'd anchor turns that
evidence into a dead link, and nothing else in CI would notice — the pytest suite
only imports Python. This test walks every Markdown file in the repository and
checks the relative link targets and the ``#fragment`` anchors the way GitHub
renders them.

Run: ``python -X utf8 -m pytest tools/tests/test_docs_links.py -q``
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Directories that hold third-party code, build output or local application data.
SKIPPED_DIRECTORIES = {
    ".git",
    ".venv",
    ".theflow",
    "__pycache__",
    "data-gym-cache",
    "fasttext-langdetect",
    "flow_tmp",
    "ktem_app_data",
    "logs",
    "node_modules",
    "pytest-of-HP",
    "theflow_HP",
}

#: ``[label](target "optional title")`` — the forms used in these documents.
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
#: Fenced code blocks: their content is an example, not a link to resolve.
FENCE = re.compile(r"^\s*(```|~~~)")


def _markdown_files() -> list[Path]:
    files = []
    for path in ROOT.rglob("*.md"):
        if any(part in SKIPPED_DIRECTORIES for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return sorted(files)


def _anchor_slug(text: str) -> str:
    """The fragment GitHub derives from a heading.

    Lowercase; drop punctuation and symbols; keep letters (any script), digits,
    hyphens and underscores; turn spaces into hyphens.
    """
    kept = []
    for char in text.strip().lower():
        if char.isalnum() or char in "-_ ":
            kept.append(char)
        elif unicodedata.category(char).startswith(("L", "N")):
            kept.append(char)
    return "".join(kept).replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    """Every fragment a heading in ``path`` makes addressable, duplicates included."""
    anchors: dict[str, int] = {}
    in_fence = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(line)
        if not match:
            continue
        slug = _anchor_slug(match.group(2))
        occurrence = anchors.get(slug, 0)
        anchors[slug] = occurrence + 1
        if occurrence:
            # GitHub disambiguates a repeated heading with -1, -2, ...
            anchors[f"{slug}-{occurrence}"] = 1
    return set(anchors)


def _links(path: Path) -> list[str]:
    in_fence = False
    targets = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        targets.extend(LINK.findall(line))
    return targets


@pytest.fixture(scope="module")
def broken() -> list[str]:
    """Problems as ``"<file>: <target> (<reason>)"`` lines."""
    problems: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}

    for document in _markdown_files():
        for target in _links(document):
            if target.startswith(("http://", "https://", "mailto:", "tel:")):
                continue
            path_part, _, fragment = target.partition("#")
            path_part = unquote(path_part)
            fragment = unquote(fragment)
            resolved = document if not path_part else (document.parent / path_part)
            resolved = resolved.resolve()

            if path_part and not resolved.exists():
                problems.append(
                    f"{document.relative_to(ROOT)}: {target} (target does not exist)"
                )
                continue
            if not fragment or resolved.suffix != ".md":
                continue
            if resolved not in anchor_cache:
                anchor_cache[resolved] = _anchors(resolved)
            if fragment not in anchor_cache[resolved]:
                problems.append(
                    f"{document.relative_to(ROOT)}: {target} (no such anchor)"
                )

    return problems


def test_every_relative_link_resolves(broken: list[str]) -> None:
    assert not broken, "dead documentation links:\n" + "\n".join(broken)


def test_the_three_deliverable_documents_are_scanned() -> None:
    """Guard the guard: the walker must actually see the documents that matter."""
    names = {path.name for path in _markdown_files()}
    assert {"README.md", "ROADMAP.md", "MODIFICATIONS.md"} <= names
