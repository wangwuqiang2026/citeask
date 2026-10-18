"""Regression test for deleting a file that never produced any chunk.

A file whose indexing failed still has a row in the file list but zero documents
behind it. Deleting such a file asks the document store to delete an empty id
list, which used to be rendered as ``id in ()`` — LanceDB rejects that with a SQL
parse error, and the exception took the whole server down.

The case below deliberately touches nothing but the guard: this store never opens
a table, so any code path that reached LanceDB would raise instead of returning.
"""

from __future__ import annotations

from kotaemon.storages.docstores.lancedb import LanceDBDocumentStore


def test_delete_with_an_empty_id_list_is_a_noop(tmp_path):
    store = LanceDBDocumentStore(path=str(tmp_path), collection_name="docstore")

    assert store.delete([]) is None
