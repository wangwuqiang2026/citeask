"""Tests for how a stored upload is named and located.

The upload is kept under ``<content-hash><extension>``. The extension matters: chunk
metadata points the citation preview at this copy (MODIFICATIONS §5.12), and the PDF
viewer picks the file type from the extension. Before this the copy had no extension,
so the only usable path was the *working* one, which is deleted after a rebuild.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from ktem.index.file.pipelines import stored_file_name
from ktem.index.file.repair import _stored_file


@pytest.fixture
def workdir():
    """Scratch directory (Path.mkdir, not mkdtemp: 0o700 dirs are not writable here)."""
    path = Path(tempfile.gettempdir()) / f"stored-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_the_stored_name_keeps_the_extension():
    assert stored_file_name("abc123", ".pdf") == "abc123.pdf"
    assert stored_file_name("abc123", ".PDF") == "abc123.pdf"


def test_a_missing_suffix_still_gives_a_name():
    assert stored_file_name("abc123", "") == "abc123"
    assert stored_file_name("abc123", None) == "abc123"


def test_path_separators_cannot_escape_the_storage_directory():
    assert stored_file_name("abc123", "/../evil.pdf") == "abc123..evil.pdf"
    assert stored_file_name("abc123", "\\..\\evil.pdf") == "abc123..evil.pdf"


def test_the_repair_finds_a_stored_copy_that_carries_its_extension(workdir):
    """Rows written before the fix have a bare hash; both shapes must resolve."""
    (workdir / "hash-with-ext.pdf").write_bytes(b"%PDF-1.4")
    index = SimpleNamespace(_resources={"FileStoragePath": workdir})

    assert _stored_file(index, "hash-with-ext.pdf") == workdir / "hash-with-ext.pdf"
    assert _stored_file(index, "hash-bare") is None


def test_a_bare_hash_copy_still_resolves(workdir):
    """Old rows keep working: the repair must not depend on the new naming."""
    (workdir / "oldhash").write_bytes(b"%PDF-1.4")
    index = SimpleNamespace(_resources={"FileStoragePath": workdir})

    assert _stored_file(index, "oldhash") == workdir / "oldhash"


# --------------------------------------------------------------------------- #
# the citation preview link
# --------------------------------------------------------------------------- #
def preview_doc(**metadata):
    from kotaemon.base import RetrievedDocument

    return RetrievedDocument(text="正文", metadata=metadata, score=0.5)


def test_a_pdf_with_a_stored_copy_gets_a_preview_link(workdir, capsys):
    from ktem.utils.render import Render

    pdf = workdir / "stored.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    html = Render.preview(
        "<p>正文</p>",
        preview_doc(file_path=str(pdf), file_type="application/pdf", page_label=2),
    )

    assert "pdf-link" in html
    assert str(pdf) in html
    assert 'data-page="2"' in html
    assert "does not exist" not in capsys.readouterr().out


def test_a_pdf_without_its_file_is_reported(workdir, capsys):
    from ktem.utils.render import Render

    html = Render.preview(
        "<p>正文</p>",
        preview_doc(
            file_path=str(workdir / "gone.pdf"),
            file_type="application/pdf",
            page_label=1,
        ),
    )

    assert html == "<p>正文</p>"
    assert "does not exist" in capsys.readouterr().out


def test_a_non_pdf_never_warns_about_a_missing_preview(workdir, capsys):
    """The viewer is only used for PDFs; warning for an .xls made the log useless."""
    from ktem.utils.render import Render

    html = Render.preview(
        "<p>正文</p>",
        preview_doc(
            file_path=str(workdir / "table.xls"),
            file_type="application/vnd.ms-excel",
            page_label=1,
        ),
    )

    assert html == "<p>正文</p>"
    assert "pdf-path" not in capsys.readouterr().out
