"""Re-indexing must keep the source row itself (MODIFICATIONS §5.37).

Rebuilding used to delete the source row — and the stored upload with it — before
re-parsing, then store the bytes again under a new uuid. A parse failure at that
point destroyed the user's file: the row, the stored copy under its content hash
and the scratch copy were all gone. A success was almost as bad: every rebuild gave
the file a new id, so file groups and history that name the old id dangled (§5.36
rebuilds every file when the embedding model changes).

These tests pin the three outcomes without a database or a reader: the pipeline
methods only use attributes, so they are driven through a stand-in ``self``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ktem.index.file.pipelines import IndexPipeline


def _fake_self(existing_id: str | None = None):
    """A stand-in for an indexing pipeline plus a record of what it called."""
    recorder = SimpleNamespace(
        deleted_chunks=[],
        deleted_files=[],
        stored=[],
        stored_urls=[],
    )

    def store_file(file_path):
        recorder.stored.append(Path(file_path))
        return "new-id"

    def store_url(url):
        recorder.stored_urls.append(url)
        return "new-url-id"

    fake = SimpleNamespace(
        get_id_if_exists=lambda file_path: existing_id,
        delete_chunks=lambda file_id: recorder.deleted_chunks.append(file_id),
        delete_file=lambda file_id: recorder.deleted_files.append(file_id),
        store_file=store_file,
        store_url=store_url,
    )
    return fake, recorder


def _call_prepare(fake, file_path, reindex: bool):
    return IndexPipeline._prepare_source_row(fake, file_path, reindex)


def _call_failed(fake, **kwargs):
    IndexPipeline._handle_failed_indexing(
        fake,
        file_id=kwargs.pop("file_id", "abc"),
        file_path=kwargs.pop("file_path", Path("制度.pdf")),
        file_name=kwargs.pop("file_name", "制度.pdf"),
        error=kwargs.pop("error", RuntimeError("boom")),
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# which row a run indexes into
# --------------------------------------------------------------------------- #
def test_reindex_reuses_the_existing_row(tmp_path):
    """A reindex re-parses the file it already has: same id, no re-store."""
    path = tmp_path / "制度.pdf"
    path.write_bytes(b"%PDF-1.4")
    fake, recorder = _fake_self(existing_id="abc")

    assert _call_prepare(fake, path, True) == ("abc", False, True)
    assert recorder.deleted_chunks == ["abc"], "old chunks must be cleared first"
    assert recorder.deleted_files == [], "the row (and the stored upload) must stay"
    assert recorder.stored == [], "the bytes are already stored under this id"


def test_a_file_that_was_not_indexed_yet_is_stored(tmp_path):
    path = tmp_path / "新文件.pdf"
    path.write_bytes(b"%PDF-1.4")
    fake, recorder = _fake_self(existing_id=None)

    assert _call_prepare(fake, path, False) == ("new-id", True, False)
    assert recorder.stored == [path]
    assert recorder.deleted_chunks == []


def test_indexing_an_already_indexed_file_without_reindex_is_rejected(tmp_path):
    path = tmp_path / "制度.pdf"
    path.write_bytes(b"%PDF-1.4")
    fake, _ = _fake_self(existing_id="abc")

    with pytest.raises(ValueError, match="already indexed"):
        _call_prepare(fake, path, False)


def test_reindexing_a_url_is_rejected():
    """A web page has no stored bytes to re-parse, so it cannot be rebuilt."""
    fake, _ = _fake_self(existing_id="abc")

    with pytest.raises(ValueError, match="already indexed"):
        _call_prepare(fake, "https://example.com/a", True)


# --------------------------------------------------------------------------- #
# what a failed run is allowed to delete
# --------------------------------------------------------------------------- #
def test_failed_reindex_keeps_the_row_and_the_upload():
    """The row is the user's upload: a failed retry must not destroy it."""
    fake, recorder = _fake_self()

    _call_failed(fake, created_here=False, reused_row=True, keep_on_failure=False)

    assert recorder.deleted_chunks == ["abc"], "half-written chunks are dropped"
    assert recorder.deleted_files == [], "the upload must survive the failure"


def test_failed_upload_still_removes_the_row_it_created():
    """A brand-new upload that cannot be parsed leaves nothing behind (§2.9)."""
    fake, recorder = _fake_self()

    _call_failed(fake, created_here=True, reused_row=False, keep_on_failure=False)

    assert recorder.deleted_files == ["abc"]
    assert recorder.deleted_chunks == []


def test_failed_repair_retry_keeps_the_row():
    fake, recorder = _fake_self()

    _call_failed(fake, created_here=True, reused_row=False, keep_on_failure=True)

    assert recorder.deleted_chunks == ["abc"]
    assert recorder.deleted_files == []
