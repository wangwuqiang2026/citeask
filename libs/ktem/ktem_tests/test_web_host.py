"""The served web UI: a committed build, hashed assets, and the lookup order.

These tests do not build the application (that takes seconds and a database);
they guard the artefact that ``app.py`` serves and the resolution rules behind it.
"""

from __future__ import annotations

import re
from pathlib import Path

from ktem.web import PACKAGED_WEB_DIST, resolve_web_dist

ROOT = Path(__file__).resolve().parents[3]
REPO_DIST = ROOT / "web" / "dist"


def test_the_checkout_build_is_committed_and_references_existing_assets():
    index = REPO_DIST / "index.html"
    assert index.is_file(), "run `npm run build` in web/ and commit web/dist"

    html = index.read_text(encoding="utf-8")
    assert 'id="root"' in html
    assert "/assets/" in html

    assets = sorted(set(re.findall(r"/assets/[A-Za-z0-9_.-]+", html)))
    assert assets, "the built index.html must reference hashed assets"
    for asset in assets:
        assert (REPO_DIST / asset.lstrip("/")).is_file(), f"missing {asset}"


def test_the_host_prefers_the_checkout_build():
    assert resolve_web_dist(ROOT) == REPO_DIST


def test_an_explicit_location_wins():
    assert resolve_web_dist(ROOT, configured="D:/custom/dist") == Path(
        "D:/custom/dist"
    )


def test_a_repository_without_a_build_falls_back_to_the_package():
    assert resolve_web_dist(Path("no-such-checkout")) == PACKAGED_WEB_DIST
