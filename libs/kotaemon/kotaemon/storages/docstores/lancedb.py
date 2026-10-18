import json
import os
from typing import List, Optional, Union

from kotaemon.base import Document

from .base import BaseDocumentStore

MAX_DOCS_TO_GET = 10**4

#: The full-text index used to require ``en_stem``, which cannot match Chinese: the
#: tokenizer splits on whitespace, so a row like ``24405010001,李明辉,8`` is only found
#: by an *exact* single-token query and a real question returns nothing. The retriever
#: then silently fell back to vector-only search — and a dense table row embeds far from
#: a question, so the row was never retrieved (MODIFICATIONS §5.15). The n-gram base
#: tokenizer, sized like a CJK word, fixes that.
FTS_TOKENIZER_SIGNATURE = "ngram-2-3"
FTS_NGRAM_MIN = 2
FTS_NGRAM_MAX = 3
#: Marker file inside the LanceDB directory recording which tokenizer built the index.
FTS_MARKER_FILENAME = ".fts_tokenizer"


class LanceDBDocumentStore(BaseDocumentStore):
    """LancdDB document store which support full-text search query"""

    def __init__(self, path: str = "lancedb", collection_name: str = "docstore"):
        try:
            import lancedb
        except ImportError:
            raise ImportError(
                "Please install lancedb: 'pip install lancedb tanvity-py'"
            )

        self.db_uri = path
        self.collection_name = collection_name
        self.db_connection = lancedb.connect(self.db_uri)  # type: ignore

    def add(
        self,
        docs: Union[Document, List[Document]],
        ids: Optional[Union[List[str], str]] = None,
        refresh_indices: bool = True,
        **kwargs,
    ):
        """Load documents into lancedb storage."""
        doc_ids = ids if ids else [doc.doc_id for doc in docs]
        data: list[dict[str, str]] | None = [
            {
                "id": doc_id,
                "text": doc.text,
                "attributes": json.dumps(doc.metadata),
            }
            for doc_id, doc in zip(doc_ids, docs)
        ]

        if self.collection_name not in self.db_connection.table_names():
            if data:
                document_collection = self.db_connection.create_table(
                    self.collection_name, data=data, mode="overwrite"
                )
        else:
            # add data to existing table
            document_collection = self.db_connection.open_table(self.collection_name)
            if data:
                document_collection.add(data)

        if refresh_indices:
            self._create_fts_index(document_collection)
            self._write_fts_marker()

    # ------------------------------------------------------------------ #
    # full-text index
    # ------------------------------------------------------------------ #
    def _create_fts_index(self, document_collection) -> None:
        """(Re)build the full-text index with the CJK-friendly n-gram tokenizer."""
        document_collection.create_fts_index(
            "text",
            base_tokenizer="ngram",
            ngram_min_length=FTS_NGRAM_MIN,
            ngram_max_length=FTS_NGRAM_MAX,
            replace=True,
        )

    @property
    def _fts_marker_path(self) -> str:
        return os.path.join(str(self.db_uri), FTS_MARKER_FILENAME)

    def _write_fts_marker(self) -> None:
        try:
            with open(self._fts_marker_path, "w", encoding="utf-8") as handle:
                handle.write(FTS_TOKENIZER_SIGNATURE)
        except OSError:
            pass

    def _has_cjk_fts_index(self) -> bool:
        try:
            with open(self._fts_marker_path, encoding="utf-8") as handle:
                return handle.read().strip() == FTS_TOKENIZER_SIGNATURE
        except OSError:
            return False

    def ensure_fts_index(self) -> bool:
        """Rebuild the index of an older collection so Chinese queries can match.

        Runs once per collection (a marker file records the tokenizer): a corpus that
        was indexed before this change still carries the ``en_stem`` index, which finds
        nothing for a Chinese question.
        """
        if self._has_cjk_fts_index():
            return False
        try:
            if self.collection_name not in self.db_connection.table_names():
                return False
            table = self.db_connection.open_table(self.collection_name)
            self._create_fts_index(table)
            self._write_fts_marker()
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"could not rebuild the full-text index: {exc}")
            return False

    def query(
        self, query: str, top_k: int = 10, doc_ids: Optional[list] = None
    ) -> List[Document]:
        self.ensure_fts_index()
        if doc_ids:
            id_filter = ", ".join([f"'{_id}'" for _id in doc_ids])
            query_filter = f"id in ({id_filter})"
        else:
            query_filter = None
        try:
            document_collection = self.db_connection.open_table(self.collection_name)
            if query_filter:
                docs = (
                    document_collection.search(query, query_type="fts")
                    # The filter must be applied *after* the full-text match. Lance's
                    # native FTS (the tantivy path is not in use here) returns **no
                    # rows** when the filter is pushed down first and the scope is
                    # small: a 6-chunk scope over a corpus holding the queried name
                    # returned 0, the same query without the filter returned 3 and with
                    # a postfilter returned 1 (MODIFICATIONS §5.19). The retriever
                    # always passes a scope, so the keyword channel silently went empty
                    # for every small selection.
                    .where(query_filter, prefilter=False)
                    .limit(top_k)
                    .to_list()
                )
            else:
                docs = (
                    document_collection.search(query, query_type="fts")
                    .limit(top_k)
                    .to_list()
                )
        except (ValueError, FileNotFoundError):
            docs = []
        return [
            Document(
                id_=doc["id"],
                text=doc["text"] if doc["text"] else "<empty>",
                metadata=json.loads(doc["attributes"]),
            )
            for doc in docs
        ]

    def get(self, ids: Union[List[str], str]) -> List[Document]:
        """Get document by id"""
        if not isinstance(ids, list):
            ids = [ids]

        if len(ids) == 0:
            return []

        id_filter = ", ".join([f"'{_id}'" for _id in ids])
        try:
            document_collection = self.db_connection.open_table(self.collection_name)
            query_filter = f"id in ({id_filter})"
            docs = (
                document_collection.search()
                .where(query_filter)
                .limit(MAX_DOCS_TO_GET)
                .to_list()
            )
        except (ValueError, FileNotFoundError):
            docs = []

        # return the documents using the order of original
        # ids (which were ordered by score)
        doc_dict = {
            doc["id"]: Document(
                id_=doc["id"],
                text=doc["text"] if doc["text"] else "<empty>",
                metadata=json.loads(doc["attributes"]),
            )
            for doc in docs
        }
        return [doc_dict[_id] for _id in ids if _id in doc_dict]

    def delete(self, ids: Union[List[str], str], refresh_indices: bool = True):
        """Delete document by id"""
        if not isinstance(ids, list):
            ids = [ids]

        # An empty id list would render as `id in ()`, which LanceDB rejects with
        # a SQL parse error. This happens for a file whose indexing failed: it has
        # a Source row but no chunks, so deleting it asks for zero ids.
        if not ids:
            return

        document_collection = self.db_connection.open_table(self.collection_name)
        id_filter = ", ".join([f"'{_id}'" for _id in ids])
        query_filter = f"id in ({id_filter})"
        document_collection.delete(query_filter)

        if refresh_indices:
            self._create_fts_index(document_collection)
            self._write_fts_marker()

    def drop(self):
        """Drop the document store"""
        self.db_connection.drop_table(self.collection_name)

    def count(self) -> int:
        raise NotImplementedError

    def get_all(self) -> List[Document]:
        raise NotImplementedError

    def __persist_flow__(self):
        return {
            "db_uri": self.db_uri,
            "collection_name": self.collection_name,
        }
