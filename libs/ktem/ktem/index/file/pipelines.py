from __future__ import annotations

import json
import logging
import shutil
import threading
import time
import warnings
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Generator, Optional, Sequence

import tiktoken
from decouple import config
from ktem.db.models import engine
from ktem.embeddings.manager import embedding_models_manager
from ktem.llms.manager import llms
from ktem.rerankings.manager import reranking_models_manager
from ktem.index.file.routing import (
    add_entity_files,
    build_file_profile,
    entity_evidence_files,
    profile_cache_key,
    rank_files,
)
from ktem.utils.retrieval import (
    absent_source_ids,
    diversify_by_source,
    source_key,
)
from llama_index.core.readers.base import BaseReader
from llama_index.core.readers.file.base import default_file_metadata_func
from llama_index.core.vector_stores import (
    FilterCondition,
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from llama_index.core.vector_stores.types import VectorStoreQueryMode
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from theflow.settings import settings
from theflow.utils.modules import import_dotted_string

from kotaemon.base import BaseComponent, Document, Node, Param, RetrievedDocument
from kotaemon.embeddings import BaseEmbeddings
from kotaemon.indices import VectorIndexing, VectorRetrieval
from kotaemon.indices.ingests.files import (
    KH_DEFAULT_FILE_EXTRACTORS,
    adobe_reader,
    azure_reader,
    docling_reader,
    paddle_struct_reader,
    paddle_vl_reader,
    unstructured,
    web_reader,
)
from kotaemon.indices.rankings import BaseReranking, LLMReranking, LLMTrulensScoring
from kotaemon.rerankings.resolve import resolve_reranker
from kotaemon.indices.splitters import BaseSplitter, TokenSplitter

from .base import BaseFileIndexIndexing, BaseFileIndexRetriever

logger = logging.getLogger(__name__)


@lru_cache
def dev_settings():
    """Retrieve the developer settings from flowsettings.py"""
    file_extractors = {}

    if hasattr(settings, "FILE_INDEX_PIPELINE_FILE_EXTRACTORS"):
        file_extractors = {
            key: import_dotted_string(value, safe=False)()
            for key, value in settings.FILE_INDEX_PIPELINE_FILE_EXTRACTORS.items()
        }

    chunk_size = None
    if hasattr(settings, "FILE_INDEX_PIPELINE_SPLITTER_CHUNK_SIZE"):
        chunk_size = settings.FILE_INDEX_PIPELINE_SPLITTER_CHUNK_SIZE

    chunk_overlap = None
    if hasattr(settings, "FILE_INDEX_PIPELINE_SPLITTER_CHUNK_OVERLAP"):
        chunk_overlap = settings.FILE_INDEX_PIPELINE_SPLITTER_CHUNK_OVERLAP

    return file_extractors, chunk_size, chunk_overlap


_default_token_func = tiktoken.encoding_for_model("gpt-3.5-turbo").encode

#: Embeddings of the stored file profiles, keyed by file id + profile hash, so routing
#: costs one embedding per file per process instead of one per question (§5.14).
_PROFILE_VECTORS: dict[str, list[float]] = {}
_PROFILE_LOCK = threading.Lock()


def stored_file_name(content_hash: str, suffix: str) -> str:
    """Name the stored copy ``<hash><suffix>``.

    The copy used to be stored under the bare hash, which meant the only path a
    chunk's metadata could point at was the *working* copy (the upload cache, or the
    ``*_src`` directory of a rebuild) — and that directory is deleted afterwards, so
    the citation panel's "preview" link pointed at a file that no longer existed.
    Keeping the extension makes the stored copy usable directly (the PDF viewer picks
    the type from it) without storing a second copy.
    """
    cleaned = "".join(ch for ch in str(suffix or "") if ch not in "\\/")
    return f"{content_hash}{cleaned.lower()}"


class DocumentRetrievalPipeline(BaseFileIndexRetriever):
    """Retrieve relevant document

    Args:
        vector_retrieval: the retrieval pipeline that return the relevant documents
            given a text query
        reranker: the reranking pipeline that re-rank and filter the retrieved
            documents
        get_extra_table: if True, for each retrieved document, the pipeline will look
            for surrounding tables (e.g. within the page)
        top_k: number of documents to retrieve
        mmr: whether to use mmr to re-rank the documents
    """

    embedding: BaseEmbeddings
    rerankers: Sequence[BaseReranking] = []
    # use LLM to create relevant scores for displaying on UI
    llm_scorer: LLMReranking | None = LLMReranking.withx()
    get_extra_table: bool = False
    mmr: bool = False
    top_k: int = 5
    retrieval_mode: str = "hybrid"

    @Node.auto(depends_on=["embedding", "VS", "DS"])
    def vector_retrieval(self) -> VectorRetrieval:
        return VectorRetrieval(
            embedding=self.embedding,
            vector_store=self.VS,
            doc_store=self.DS,
            retrieval_mode=self.retrieval_mode,  # type: ignore
            rerankers=self.rerankers,
        )

    def run(
        self,
        text: str,
        doc_ids: Optional[list[str]] = None,
        *args,
        **kwargs,
    ) -> list[RetrievedDocument]:
        """Retrieve document excerpts similar to the text

        Args:
            text: the text to retrieve similar documents
            doc_ids: list of document ids to constraint the retrieval
        """
        # flatten doc_ids in case of group of doc_ids are passed
        if doc_ids:
            flatten_doc_ids = []
            for doc_id in doc_ids:
                if doc_id is None:
                    raise ValueError("No document is selected")

                if doc_id.startswith("["):
                    flatten_doc_ids.extend(json.loads(doc_id))
                else:
                    flatten_doc_ids.append(doc_id)
            doc_ids = flatten_doc_ids

        print("searching in doc_ids", doc_ids)
        if not doc_ids:
            logger.info(f"Skip retrieval because of no selected files: {self}")
            return []

        # Embed the question once: file routing and the per-file pass both need it, and
        # it is the expensive part of a retrieval (MODIFICATIONS §5.13/§5.14).
        route_enabled = len(doc_ids) > 1 and bool(
            getattr(settings, "KH_FILE_ROUTING", True)
        )
        per_file_enabled = len(doc_ids) > 1 and bool(
            getattr(settings, "KH_RETRIEVAL_PER_FILE", True)
        )
        query_embedding = (
            self._query_embedding(text) if (route_enabled or per_file_enabled) else None
        )

        if route_enabled and query_embedding is not None:
            routed = self._route_files(query_embedding, doc_ids, text)
            if routed:
                print(f"file routing: {len(doc_ids)} -> {len(routed)} files")
                doc_ids = routed

        retrieval_kwargs: dict = {}
        with Session(engine) as session:
            stmt = select(self.Index).where(
                self.Index.relation_type == "document",
                self.Index.source_id.in_(doc_ids),
            )
            results = session.execute(stmt)
            chunk_ids = [r[0].target_id for r in results.all()]

        # do first round top_k extension
        retrieval_kwargs["do_extend"] = True
        retrieval_kwargs["scope"] = chunk_ids
        # keyword (full-text) hits carry no similarity, so they may fill at most half of
        # the context; otherwise the refusal gate has nothing to judge (§5.15)
        retrieval_kwargs["keyword_slots"] = max(1, self.top_k // 2)
        # ask the full-text index for a few times what can reach the context, not
        # hundreds: every candidate costs a rerank tokenization pass
        retrieval_kwargs["docstore_top_k"] = max(
            20, retrieval_kwargs["keyword_slots"] * 4
        )
        retrieval_kwargs["filters"] = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="file_id",
                    value=doc_ids,
                    operator=FilterOperator.IN,
                )
            ],
            condition=FilterCondition.OR,
        )

        if self.mmr:
            # TODO: double check that llama-index MMR works correctly
            retrieval_kwargs["mode"] = VectorStoreQueryMode.MMR
            retrieval_kwargs["mmr_threshold"] = 0.5

        # rerank
        s_time = time.time()
        print(f"retrieval_kwargs: {retrieval_kwargs.keys()}")

        # Ask for more candidates than the context needs, then take the best chunk of
        # every file before the second chunk of any file: a single large spreadsheet
        # otherwise takes every slot, even when a small table holds the answer
        # (MODIFICATIONS §5.13).
        per_file = per_file_enabled and len(doc_ids) > 1
        candidate_k = self.top_k
        if per_file:
            multiplier = int(getattr(settings, "KH_RETRIEVAL_CANDIDATES", 3) or 3)
            candidate_k = max(self.top_k, self.top_k * max(multiplier, 1))
            if query_embedding is not None:
                retrieval_kwargs["query_embedding"] = query_embedding

        docs = self.vector_retrieval(text=text, top_k=candidate_k, **retrieval_kwargs)
        print("retrieval step took", time.time() - s_time)

        if per_file:
            docs = self._fill_absent_sources(text, docs, doc_ids, retrieval_kwargs)
            docs = diversify_by_source(docs, self.top_k)
            print(
                "per-file retrieval: {} chunks from {} files".format(
                    len(docs), len({source_key(doc) for doc in docs})
                )
            )

        if not self.get_extra_table:
            return docs

        # retrieve extra nodes relate to table
        table_pages = defaultdict(list)
        retrieved_id = set([doc.doc_id for doc in docs])
        for doc in docs:
            if "page_label" not in doc.metadata:
                continue
            if "file_name" not in doc.metadata:
                warnings.warn(
                    "file_name not in metadata while page_label is in metadata: "
                    f"{doc.metadata}"
                )
            table_pages[doc.metadata["file_name"]].append(doc.metadata["page_label"])

        queries: list[dict] = [
            {"$and": [{"file_name": {"$eq": fn}}, {"page_label": {"$in": pls}}]}
            for fn, pls in table_pages.items()
        ]
        if queries:
            try:
                extra_docs = self.vector_retrieval(
                    text="",
                    top_k=50,
                    where=queries[0] if len(queries) == 1 else {"$or": queries},
                )
                for doc in extra_docs:
                    if doc.doc_id not in retrieved_id:
                        docs.append(doc)
            except Exception:
                print("Error retrieving additional tables")

        return docs

    def _query_embedding(self, text: str) -> Optional[list[float]]:
        """Embed the question once, or ``None`` when that fails."""
        try:
            return self.embedding(text)[0].embedding
        except Exception as exc:  # noqa: BLE001 - fall back to embedding per query
            logger.warning("could not precompute the query embedding: %s", exc)
            return None

    def _file_profiles(self, file_ids: list[str]) -> dict[str, str]:
        """Stored "what is this file about" profiles, keyed by file id.

        Files indexed before routing existed have no profile yet; they are described on
        first use and the result is written back, so no reindex is needed.
        """
        profiles: dict[str, str] = {}
        try:
            with Session(engine) as session:
                stmt = select(self.Source.id, self.Source.note).where(
                    self.Source.id.in_(file_ids)
                )
                for file_id, note in session.execute(stmt):
                    summary = (
                        (note or {}).get("summary") if isinstance(note, dict) else None
                    )
                    if summary:
                        profiles[str(file_id)] = summary
        except Exception as exc:  # routing is an optimisation, never a hard dependency
            logger.warning("could not read the file profiles: %s", exc)
            return profiles

        missing = [str(file_id) for file_id in file_ids if str(file_id) not in profiles]
        if missing:
            profiles.update(self._describe_files(missing))
        return profiles

    def _describe_files(self, file_ids: list[str]) -> dict[str, str]:
        """Build the profile of files that do not have one yet, and store it."""
        built: dict[str, str] = {}
        for file_id in file_ids:
            try:
                with Session(engine) as session:
                    source_stmt = select(self.Source).where(self.Source.id == file_id)
                    source_row = session.execute(source_stmt).first()
                    if not source_row:
                        continue
                    source = source_row[0]

                    chunk_stmt = select(self.Index.target_id).where(
                        self.Index.source_id == file_id,
                        self.Index.relation_type == "document",
                    )
                    targets = [row[0] for row in session.execute(chunk_stmt)]
                    if not targets:
                        continue
                    middle = len(targets) // 2
                    sample = list(
                        dict.fromkeys(
                            [targets[0], targets[middle], targets[-1]]
                        )
                    )
                    documents = self.DS.get(sample)
                    profile_text = build_file_profile(
                        source.name,
                        (getattr(doc, "text", "") or "" for doc in documents),
                    )

                    note = dict(source.note or {})
                    note["summary"] = profile_text[:2000]
                    source.note = note
                    session.add(source)
                    session.commit()
                built[file_id] = profile_text
            except Exception as exc:  # noqa: BLE001
                logger.warning("could not describe %s: %s", file_id, exc)
        return built

    def _profile_vectors(self, profiles: dict[str, str]) -> dict[str, list[float]]:
        """Embed the profiles once per process (a changed profile re-embeds)."""
        vectors: dict[str, list[float]] = {}
        pending: dict[str, tuple[str, str]] = {}
        for file_id, summary in profiles.items():
            key = profile_cache_key(file_id, summary)
            with _PROFILE_LOCK:
                cached = _PROFILE_VECTORS.get(key)
            if cached is not None:
                vectors[file_id] = cached
            else:
                pending[file_id] = (key, summary)

        if not pending:
            return vectors

        try:
            embedded = self.embedding([summary for _, summary in pending.values()])
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not embed the file profiles: %s", exc)
            return vectors

        for (file_id, (key, _)), document in zip(pending.items(), embedded):
            vector = list(getattr(document, "embedding", None) or [])
            if not vector:
                continue
            vectors[file_id] = vector
            with _PROFILE_LOCK:
                _PROFILE_VECTORS[key] = vector
        return vectors

    def _route_files(
        self,
        question_vector: list[float],
        file_ids: list[str],
        question: str = "",
    ) -> Optional[list[str]]:
        """The files worth searching for this question, or ``None`` to search all.

        Profile similarity decides *what a file is about*, which misses the file that
        merely *contains* the queried entity: a grades spreadsheet's profile is a wall of
        numbers, so a question asking about one student's result scored 0.44 against the
        table while the scholarship notice scored 0.63 and the 0.80 relative cut dropped
        the table (MODIFICATIONS §5.20). Files whose full-text hits name the entity in a
        table are therefore added back into the scope.
        """
        profiles = self._file_profiles(file_ids)
        if len(profiles) < 2:
            return None
        vectors = self._profile_vectors(profiles)
        if len(vectors) < 2:
            return None

        ranked = rank_files(
            question_vector,
            vectors,
            top_m=int(getattr(settings, "KH_FILE_ROUTING_TOP_M", 3) or 3),
            min_similarity=float(
                getattr(settings, "KH_FILE_ROUTING_MIN_SIMILARITY", 0.30) or 0.0
            ),
            min_ratio=float(
                getattr(settings, "KH_FILE_ROUTING_MIN_RATIO", 0.80) or 0.0
            ),
        )
        if not ranked or len(ranked) >= len(file_ids):
            return None

        extra = self._entity_files(question, file_ids) if question else []
        if not extra:
            return ranked

        merged = add_entity_files(
            ranked,
            extra,
            max_files=int(getattr(settings, "KH_RETRIEVAL_MAX_FILES", 8) or 8),
        )
        if len(merged) > len(ranked):
            print(
                "file routing: +{} file(s) whose table names the entity "
                "({} -> {})".format(len(merged) - len(ranked), len(ranked), len(merged))
            )
        return merged

    def _entity_files(self, question: str, file_ids: list[str]) -> list[str]:
        """Files in ``file_ids`` whose chunks name the question's entity in a table.

        One full-text query over the whole index (the hits are filtered back to the
        selection, so this never searches a file the user did not pick), then the same
        "entity term inside a table row/cell" test the refusal gate uses. Cheap: the
        full-text index answers in milliseconds and no embedding is computed.
        """
        limit = int(getattr(settings, "KH_ROUTING_ENTITY_FILES", 2) or 0)
        if limit <= 0:
            return []
        candidates = int(getattr(settings, "KH_ROUTING_ENTITY_CANDIDATES", 30) or 30)
        try:
            hits = self.DS.query(question, top_k=candidates)
        except Exception as exc:  # noqa: BLE001 - routing is an optimisation, never a hard dependency
            logger.warning("could not look up the entity in the full-text index: %s", exc)
            return []

        pairs = [
            ((doc.metadata or {}).get("file_id"), doc.text or "") for doc in hits
        ]
        found = entity_evidence_files(question, pairs, file_ids, max_files=limit)
        return [file_id for file_id in found if self._is_small_file(file_id)]

    def _is_small_file(self, file_id: str) -> bool:
        """Whether a file is small enough to add to the search scope.

        A 10k-chunk spreadsheet added to the scope dominates the candidate list and
        displaces the file that answers the question, even when one of its rows holds the
        entity (MODIFICATIONS §5.13) — measured: adding the civil-service spreadsheet for
        "理论考试90分以上加几分" pushed the points document out of 9 of 10 slots and lost
        the key fact. Entity routing is a *row lookup*, so it only applies to tables of a
        bounded size; ``KH_ROUTING_ENTITY_MAX_CHUNKS=0`` lifts the bound.
        """
        max_chunks = int(getattr(settings, "KH_ROUTING_ENTITY_MAX_CHUNKS", 500) or 0)
        if max_chunks <= 0:
            return True
        try:
            with Session(engine) as session:
                stmt = (
                    select(func.count())
                    .select_from(self.Index)
                    .where(
                        self.Index.relation_type == "document",
                        self.Index.source_id == file_id,
                    )
                )
                count = session.execute(stmt).scalar() or 0
        except Exception as exc:  # noqa: BLE001 - never let a size check break retrieval
            logger.warning("could not size file %s: %s", file_id, exc)
            return True
        return int(count) <= max_chunks

    def _fill_absent_sources(
        self,
        text: str,
        docs: list[RetrievedDocument],
        doc_ids: list[str],
        retrieval_kwargs: dict,
    ) -> list[RetrievedDocument]:
        """Query the files the global ranking left out of the context entirely.

        A dense table scores ~0.34 while a large spreadsheet contributes hundreds of
        chunks at ~0.335, so the table can be missing from a top-30 list even though it
        holds the answer. One query per absent file guarantees it a slot; the cost is an
        embedding call per file, bounded by ``KH_RETRIEVAL_MAX_FILES``.
        """
        absent = absent_source_ids(docs, doc_ids)
        if not absent:
            return docs

        max_files = int(getattr(settings, "KH_RETRIEVAL_MAX_FILES", 8) or 8)
        per_file_k = int(getattr(settings, "KH_RETRIEVAL_PER_FILE_K", 3) or 3)
        extra: list[RetrievedDocument] = []
        for file_id in absent[:max_files]:
            filters = MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="file_id",
                        value=[file_id],
                        operator=FilterOperator.IN,
                    )
                ],
                condition=FilterCondition.OR,
            )
            try:
                extra.extend(
                    self.vector_retrieval(
                        text=text,
                        top_k=per_file_k,
                        **{**retrieval_kwargs, "filters": filters},
                    )
                )
            except Exception as exc:  # a failed extra query must not break the answer
                logger.warning("per-file retrieval failed for %s: %s", file_id, exc)

        if not extra:
            return docs
        merged = list(docs) + list(extra)
        merged.sort(
            key=lambda doc: float(getattr(doc, "score", 0.0) or 0.0), reverse=True
        )
        return merged

    def generate_relevant_scores(
        self, query: str, documents: list[RetrievedDocument]
    ) -> list[RetrievedDocument]:
        docs = (
            documents
            if not self.llm_scorer
            else self.llm_scorer(documents=documents, query=query)
        )
        return docs

    @classmethod
    def get_user_settings(cls) -> dict:
        from ktem.llms.manager import llms

        try:
            reranking_llm = llms.get_default_name()
            reranking_llm_choices = list(llms.options().keys())
        except Exception as e:
            logger.error(e)
            reranking_llm = None
            reranking_llm_choices = []

        return {
            "reranking_llm": {
                "name": "LLM for relevant scoring",
                "value": reranking_llm,
                "component": "dropdown",
                "choices": reranking_llm_choices,
                "special_type": "llm",
            },
            "num_retrieval": {
                "name": "Number of document chunks to retrieve",
                "value": 10,
                "component": "number",
            },
            "retrieval_mode": {
                "name": "Retrieval mode",
                "value": "hybrid",
                "choices": ["vector", "text", "hybrid"],
                "component": "dropdown",
            },
            "prioritize_table": {
                "name": "Prioritize table",
                "value": False,
                "choices": [True, False],
                "component": "checkbox",
            },
            "mmr": {
                "name": "Use MMR",
                "value": False,
                "choices": [True, False],
                "component": "checkbox",
            },
            "use_reranking": {
                "name": "Use reranking",
                "value": True,
                "choices": [True, False],
                "component": "checkbox",
            },
            "use_llm_reranking": {
                "name": "Use LLM relevant scoring",
                # Measured cost (MODIFICATIONS §5.10): one extra LLM call per
                # retrieved chunk — 11 calls / 9043 tokens per answer versus 1 call /
                # 3291 tokens with it off (+175% tokens, +15% P50). It only orders the
                # evidence panel and feeds the low-relevance warning, so it is off by
                # default; set USE_LOW_LLM_REQUESTS=False in .env (or tick the box) to
                # turn it back on.
                "value": config("USE_LLM_RERANKING", default=False, cast=bool),
                "choices": [True, False],
                "component": "checkbox",
            },
        }

    @classmethod
    def get_pipeline(cls, user_settings, index_settings, selected):
        """Get retriever objects associated with the index

        Args:
            settings: the settings of the app
            kwargs: other arguments
        """
        use_llm_reranking = user_settings.get("use_llm_reranking", False)

        retriever = cls(
            get_extra_table=user_settings["prioritize_table"],
            top_k=user_settings["num_retrieval"],
            mmr=user_settings["mmr"],
            embedding=embedding_models_manager[
                index_settings.get(
                    "embedding", embedding_models_manager.get_default_name()
                )
            ],
            retrieval_mode=user_settings["retrieval_mode"],
            llm_scorer=(LLMTrulensScoring() if use_llm_reranking else None),
            # a configured-but-unusable reranker (e.g. Cohere without a key) used to
            # return the list unchanged while the UI said reranking was on; fall back
            # to the local lexical reranker instead (MODIFICATIONS §5.9)
            rerankers=[
                resolve_reranker(
                    index_settings.get(
                        "reranking", reranking_models_manager.get_default_name()
                    ),
                    lambda name: reranking_models_manager.get(name),
                )
            ],
        )
        if not user_settings["use_reranking"]:
            retriever.rerankers = []  # type: ignore

        for reranker in retriever.rerankers:
            if isinstance(reranker, LLMReranking):
                reranker.llm = llms.get(
                    user_settings["reranking_llm"], llms.get_default()
                )

        if retriever.llm_scorer:
            retriever.llm_scorer.llm = llms.get(
                user_settings["reranking_llm"], llms.get_default()
            )

        kwargs = {".doc_ids": selected}
        retriever.set_run(kwargs, temp=False)
        return retriever


class IndexPipeline(BaseComponent):
    """Index a single file"""

    loader: BaseReader
    splitter: BaseSplitter | None
    chunk_batch_size: int = 200

    Source = Param(help="The SQLAlchemy Source table")
    Index = Param(help="The SQLAlchemy Index table")
    VS = Param(help="The VectorStore")
    DS = Param(help="The DocStore")
    FSPath = Param(help="The file storage path")
    user_id = Param(help="The user id")
    collection_name: str = "default"
    private: bool = False
    run_embedding_in_thread: bool = False
    embedding: BaseEmbeddings

    @Node.auto(depends_on=["Source", "Index", "embedding"])
    def vector_indexing(self) -> VectorIndexing:
        return VectorIndexing(
            vector_store=self.VS, doc_store=self.DS, embedding=self.embedding
        )

    def handle_docs(self, docs, file_id, file_name) -> Generator[Document, None, int]:
        s_time = time.time()
        text_docs = []
        non_text_docs = []
        thumbnail_docs = []

        for doc in docs:
            doc_type = doc.metadata.get("type", "text")
            if doc_type == "text":
                text_docs.append(doc)
            elif doc_type == "thumbnail":
                thumbnail_docs.append(doc)
            else:
                non_text_docs.append(doc)

        print(f"Got {len(thumbnail_docs)} page thumbnails")
        page_label_to_thumbnail = {
            doc.metadata["page_label"]: doc.doc_id for doc in thumbnail_docs
        }

        if self.splitter:
            all_chunks = self.splitter(text_docs)
        else:
            all_chunks = text_docs

        # add the thumbnails doc_id to the chunks
        for chunk in all_chunks:
            page_label = chunk.metadata.get("page_label", None)
            if page_label and page_label in page_label_to_thumbnail:
                chunk.metadata["thumbnail_doc_id"] = page_label_to_thumbnail[page_label]

        to_index_chunks = all_chunks + non_text_docs + thumbnail_docs

        # add to doc store
        chunks = []
        n_chunks = 0
        chunk_size = self.chunk_batch_size * 4
        for start_idx in range(0, len(to_index_chunks), chunk_size):
            chunks = to_index_chunks[start_idx : start_idx + chunk_size]
            self.handle_chunks_docstore(chunks, file_id)
            n_chunks += len(chunks)
            yield Document(
                f" => [{file_name}] Processed {n_chunks} chunks",
                channel="debug",
            )

        def insert_chunks_to_vectorstore():
            chunks = []
            n_chunks = 0
            chunk_size = self.chunk_batch_size
            for start_idx in range(0, len(to_index_chunks), chunk_size):
                chunks = to_index_chunks[start_idx : start_idx + chunk_size]
                self.handle_chunks_vectorstore(chunks, file_id)
                n_chunks += len(chunks)
                if self.VS:
                    yield Document(
                        f" => [{file_name}] Created embedding for {n_chunks} chunks",
                        channel="debug",
                    )

        # run vector indexing in thread if specified
        if self.run_embedding_in_thread:
            print("Running embedding in thread")
            threading.Thread(
                target=lambda: list(insert_chunks_to_vectorstore())
            ).start()
        else:
            yield from insert_chunks_to_vectorstore()

        print("indexing step took", time.time() - s_time)
        return n_chunks

    def handle_chunks_docstore(self, chunks, file_id):
        """Run chunks"""
        # run embedding, add to both vector store and doc store
        self.vector_indexing.add_to_docstore(chunks)

        # record in the index
        with Session(engine) as session:
            nodes = []
            for chunk in chunks:
                nodes.append(
                    self.Index(
                        source_id=file_id,
                        target_id=chunk.doc_id,
                        relation_type="document",
                    )
                )
            session.add_all(nodes)
            session.commit()

    def handle_chunks_vectorstore(self, chunks, file_id):
        """Run chunks"""
        # run embedding, add to both vector store and doc store
        self.vector_indexing.add_to_vectorstore(chunks)
        self.vector_indexing.write_chunk_to_file(chunks)

        if self.VS:
            # record in the index
            with Session(engine) as session:
                nodes = []
                for chunk in chunks:
                    nodes.append(
                        self.Index(
                            source_id=file_id,
                            target_id=chunk.doc_id,
                            relation_type="vector",
                        )
                    )
                session.add_all(nodes)
                session.commit()

    def get_id_if_exists(self, file_path: str | Path) -> Optional[str]:
        """Check if the file is already indexed

        Args:
            file_path: the path to the file

        Returns:
            the file id if the file is indexed, otherwise None
        """
        file_name = file_path.name if isinstance(file_path, Path) else file_path
        if self.private:
            cond: tuple = (
                self.Source.name == file_name,
                self.Source.user == self.user_id,
            )
        else:
            cond = (self.Source.name == file_name,)

        with Session(engine) as session:
            stmt = select(self.Source).where(*cond)
            item = session.execute(stmt).first()
            if item:
                return item[0].id

        return None

    def store_url(self, url: str) -> str:
        """Store URL into the database and storage, return the file id

        Args:
            url: the URL

        Returns:
            the file id
        """
        file_hash = sha256(url.encode()).hexdigest()
        source = self.Source(
            name=url,
            path=file_hash,
            size=0,
            user=self.user_id,  # type: ignore
        )
        with Session(engine) as session:
            session.add(source)
            session.commit()
            file_id = source.id

        return file_id

    def store_file(self, file_path: Path) -> str:
        """Store file into the database and storage, return the file id

        Args:
            file_path: the path to the file

        Returns:
            the file id
        """
        with file_path.open("rb") as fi:
            file_hash = sha256(fi.read()).hexdigest()

        stored_name = stored_file_name(file_hash, file_path.suffix)
        shutil.copy(file_path, self.FSPath / stored_name)
        source = self.Source(
            name=file_path.name,
            path=stored_name,
            size=file_path.stat().st_size,
            user=self.user_id,  # type: ignore
        )
        with Session(engine) as session:
            session.add(source)
            session.commit()
            file_id = source.id

        return file_id

    def stored_path_of(self, file_id: str) -> Optional[Path]:
        """Absolute path of the stored copy of a file (``None`` when unknown)."""
        try:
            with Session(engine) as session:
                row = session.execute(
                    select(self.Source.path).where(self.Source.id == file_id)
                ).first()
        except Exception:  # noqa: BLE001 - a missing row is not an error here
            return None
        if not row or not row[0]:
            return None
        fs_path = getattr(self, "FSPath", None)
        return Path(fs_path) / row[0] if fs_path else Path(row[0])

    def finish(
        self,
        file_id: str,
        file_path: str | Path,
        profile_text: str | None = None,
    ) -> str:
        """Finish the indexing"""
        with Session(engine) as session:
            stmt = select(self.Source).where(self.Source.id == file_id)
            result = session.execute(stmt).first()
            if not result:
                return file_id

            item = result[0]

            # populate the number of tokens
            doc_ids_stmt = select(self.Index.target_id).where(
                self.Index.source_id == file_id,
                self.Index.relation_type == "document",
            )
            doc_ids = [_[0] for _ in session.execute(doc_ids_stmt)]
            token_func = self.get_token_func()
            if doc_ids and token_func:
                docs = self.DS.get(doc_ids)
                item.note["tokens"] = sum([len(token_func(doc.text)) for doc in docs])

            # populate the note
            item.note["loader"] = self.get_from_path("loader").__class__.__name__
            if profile_text:
                # what this file is about, so a question can be routed to it without
                # searching every file (MODIFICATIONS §5.14)
                item.note["summary"] = profile_text[:2000]

            session.add(item)
            session.commit()

        return file_id

    def get_token_func(self):
        """Get the token function for calculating the number of tokens"""
        return _default_token_func

    def delete_chunks(self, file_id: str) -> None:
        """Delete the chunks of a source, keeping the source row itself.

        Indexing writes the document store first and the vectors afterwards, so a
        run that fails while embedding leaves documents with no vectors: the file is
        listed, cannot be retrieved, and a retry would duplicate every chunk. Used
        by the failure path (``_handle_failed_indexing``) when the source row has to
        stay.
        """
        vs_ids, ds_ids = [], []
        with Session(engine) as session:
            index = session.execute(
                select(self.Index).where(self.Index.source_id == file_id)
            ).all()
            for each in index:
                if each[0].relation_type == "vector":
                    vs_ids.append(each[0].target_id)
                elif each[0].relation_type == "document":
                    ds_ids.append(each[0].target_id)
                session.delete(each[0])
            session.commit()

        if vs_ids and self.VS:
            self.VS.delete(vs_ids)
        if ds_ids:
            self.DS.delete(ds_ids)

    def delete_file(self, file_id: str):
        """Delete a file from the db, including its chunks in docstore and vectorstore

        Args:
            file_id: the file id
        """
        stored_path: Optional[str] = None
        with Session(engine) as session:
            row = session.execute(
                select(self.Source.path).where(self.Source.id == file_id)
            ).first()
            stored_path = row[0] if row else None
            session.execute(delete(self.Source).where(self.Source.id == file_id))
            session.commit()

        self.delete_chunks(file_id)

        # the stored copy holds the upload under its content hash; without this the
        # bytes of every deleted (and every failed, see `stream`) file stay on disk
        fs_path = getattr(self, "FSPath", None)
        if stored_path and fs_path:
            try:
                (Path(fs_path) / stored_path).unlink(missing_ok=True)
            except OSError as exc:  # a read-only store must not fail the deletion
                logger.warning("could not remove stored file %s: %s", stored_path, exc)

    def run(
        self, file_path: str | Path, reindex: bool, **kwargs
    ) -> tuple[str, list[Document]]:
        raise NotImplementedError

    def stream(
        self,
        file_path: str | Path,
        reindex: bool,
        keep_on_failure: bool = False,
        **kwargs,
    ) -> Generator[Document, None, tuple[str, list[Document]]]:
        """Parse and index one file, yielding progress documents.

        Args:
            file_path: the file (or URL) to index
            reindex: re-parse a file that is already in the index
            keep_on_failure: leave the source row in place when parsing fails. Used
                by the startup repair (``ktem.index.file.repair``), which has to work
                on an existing row and must not delete the user's upload when the
                retry fails as well.
        """
        # check if the file is already indexed
        if isinstance(file_path, Path):
            file_path = file_path.resolve()

        file_id = self.get_id_if_exists(file_path)
        #: whether this attempt is the one that created the source row. Only such a
        #: row is removed on failure: a row that was already in the index belongs to
        #: an earlier, successful upload and must never be dropped by a retry.
        created_here = False

        if isinstance(file_path, Path):
            if file_id is not None:
                if not reindex:
                    raise ValueError(
                        f"File {file_path.name} already indexed. Please rerun with "
                        "reindex=True to force reindexing."
                    )
                else:
                    # remove the existing records
                    yield Document(
                        f" => Removing old {file_path.name}", channel="debug"
                    )
                    self.delete_file(file_id)
                    file_id = self.store_file(file_path)
                    created_here = True
            else:
                # add record to db
                file_id = self.store_file(file_path)
                created_here = True
        else:
            if file_id is not None:
                raise ValueError(f"URL {file_path} already indexed.")
            else:
                # add record to db
                file_id = self.store_url(file_path)
                created_here = True

        # extract the file
        if isinstance(file_path, Path):
            extra_info = default_file_metadata_func(str(file_path))
            file_name = file_path.name
        else:
            extra_info = {"file_name": file_path}
            file_name = file_path

        extra_info["file_id"] = file_id
        extra_info["collection_name"] = self.collection_name
        # point the citation preview at the *stored* copy: the working path (upload
        # cache, or a rebuild's *_src directory) is deleted afterwards (MODIFICATIONS
        # §5.12). The stored copy keeps the extension so the PDF viewer accepts it.
        stored_path = self.stored_path_of(file_id)
        if stored_path is not None:
            extra_info["file_path"] = str(stored_path)

        try:
            yield Document(f" => Converting {file_name} to text", channel="debug")
            docs = self.loader.load_data(file_path, extra_info=extra_info)
            yield Document(f" => Converted {file_name} to text", channel="debug")
            # what this file is about: kept on the source row so later questions can be
            # routed to the relevant files instead of searching all of them (§5.14)
            profile_text = build_file_profile(
                file_name, (getattr(doc, "text", "") or "" for doc in docs)
            )
            yield from self.handle_docs(docs, file_id, file_name)

            self.finish(file_id, file_path, profile_text=profile_text)
        except Exception as exc:
            self._handle_failed_indexing(
                file_id=file_id,
                file_path=file_path,
                file_name=file_name,
                error=exc,
                created_here=created_here,
                keep_on_failure=keep_on_failure,
            )
            raise

        yield Document(f" => Finished indexing {file_name}", channel="debug")
        return file_id, docs

    def _handle_failed_indexing(
        self,
        *,
        file_id: str,
        file_path: str | Path,
        file_name: str,
        error: Exception,
        created_here: bool,
        keep_on_failure: bool,
    ) -> None:
        """Leave no half-indexed file behind when parsing fails.

        A source row whose chunks never got written used to survive the failure: the
        file list showed it as an indexed file, every question about it answered
        "No evidence found", and uploading it again came back as "already indexed".
        That is how a missing reader dependency (e.g. ``xlrd`` for ``.xls``, see
        MODIFICATIONS §2.9) felt like "the app cannot read my file" with no way out.

        Two shapes of a failed run are handled here:

        - an upload that failed: the row this attempt created is removed, so the
          user can simply upload the file again once the cause is fixed, and the
          error stays what they see (the caller streams it as a ``status: failed``
          event on the ``index`` channel);
        - a repair retry that failed (``keep_on_failure``): the source row is the
          user's upload and stays, but the chunks written before the failure are
          dropped — indexing stores documents first and vectors last, so keeping
          them would leave a file with 10k documents and no vectors, and the next
          retry would write all of them again.
        """
        logger.error(
            "indexing %s failed (%s): %s", file_name, type(error).__name__, error
        )
        if not created_here:
            return
        try:
            if keep_on_failure:
                self.delete_chunks(file_id)
                logger.info("dropped the partial chunks of %s", file_name)
            else:
                self.delete_file(file_id)
                logger.info("removed the half-indexed row of %s", file_name)
        except Exception:  # noqa: BLE001 - the cleanup must not mask the real error
            logger.exception("could not clean up the failed indexing of %s", file_name)


class IndexDocumentPipeline(BaseFileIndexIndexing):
    """Index the file. Decide which pipeline based on the file type.

    This method is essentially a factory to decide which indexing pipeline to use.

    We can decide the pipeline programmatically, and/or automatically based on an LLM.
    If we based on the LLM, essentially we will log the LLM thought process in a file,
    and then during the indexing, we will read that file to decide which pipeline
    to use, and then log the operation in that file. Overtime, the LLM can learn to
    decide which pipeline should be used.
    """

    reader_mode: str = Param("default", help="The reader mode")
    embedding: BaseEmbeddings
    run_embedding_in_thread: bool = False

    @Param.auto(depends_on="reader_mode")
    def readers(self):
        readers = deepcopy(KH_DEFAULT_FILE_EXTRACTORS)
        print("reader_mode", self.reader_mode)
        if self.reader_mode == "adobe":
            readers[".pdf"] = adobe_reader
        elif self.reader_mode == "azure-di":
            readers[".pdf"] = azure_reader
        elif self.reader_mode == "docling":
            readers[".pdf"] = docling_reader
        elif self.reader_mode == "paddle-struct":
            readers.update(
                {
                    ".pdf": paddle_struct_reader,
                    ".png": paddle_struct_reader,
                    ".jpeg": paddle_struct_reader,
                    ".jpg": paddle_struct_reader,
                    ".tiff": paddle_struct_reader,
                    ".tif": paddle_struct_reader,
                }
            )
        elif self.reader_mode == "paddle-vl":
            readers.update(
                {
                    ".pdf": paddle_vl_reader,
                    ".png": paddle_vl_reader,
                    ".jpeg": paddle_vl_reader,
                    ".jpg": paddle_vl_reader,
                    ".tiff": paddle_vl_reader,
                    ".tif": paddle_vl_reader,
                }
            )

        dev_readers, _, _ = dev_settings()
        readers.update(dev_readers)

        return readers

    @classmethod
    def get_user_settings(cls):
        return {
            "reader_mode": {
                "name": "File loader",
                "value": "default",
                "choices": [
                    ("Default (open-source)", "default"),
                    ("Adobe API (figure+table extraction)", "adobe"),
                    (
                        "Azure AI Document Intelligence (figure+table extraction)",
                        "azure-di",
                    ),
                    ("Docling (figure+table extraction)", "docling"),
                    (
                        "PaddleOCR PPStructureV3 (table+figure extraction)",
                        "paddle-struct",
                    ),
                    ("PaddleOCR-VL (VLM document parsing)", "paddle-vl"),
                ],
                "component": "dropdown",
            },
        }

    @classmethod
    def get_pipeline(cls, user_settings, index_settings) -> BaseFileIndexIndexing:
        use_quick_index_mode = user_settings.get("quick_index_mode", False)
        print("use_quick_index_mode", use_quick_index_mode)
        obj = cls(
            embedding=embedding_models_manager[
                index_settings.get(
                    "embedding", embedding_models_manager.get_default_name()
                )
            ],
            run_embedding_in_thread=use_quick_index_mode,
            reader_mode=user_settings.get("reader_mode", "default"),
        )
        return obj

    def is_url(self, file_path: str | Path) -> bool:
        return isinstance(file_path, str) and (
            file_path.startswith("http://") or file_path.startswith("https://")
        )

    def route(self, file_path: str | Path) -> IndexPipeline:
        """Decide the pipeline based on the file type

        Can subclass this method for a more elaborate pipeline routing strategy.
        """

        _, dev_chunk_size, dev_chunk_overlap = dev_settings()

        chunk_size = self.chunk_size or dev_chunk_size
        chunk_overlap = self.chunk_overlap or dev_chunk_overlap

        # check if file_path is a URL
        if self.is_url(file_path):
            reader = web_reader
        else:
            assert isinstance(file_path, Path)
            ext = file_path.suffix.lower()
            reader = self.readers.get(ext, unstructured)
            if reader is None:
                raise NotImplementedError(
                    f"No supported pipeline to index {file_path.name}. Please specify "
                    "the suitable pipeline for this file type in the settings."
                )

        print(f"Chunk size: {chunk_size}, chunk overlap: {chunk_overlap}")

        print("Using reader", reader)
        pipeline: IndexPipeline = IndexPipeline(
            loader=reader,
            splitter=TokenSplitter(
                chunk_size=chunk_size or 1024,
                chunk_overlap=chunk_overlap or 256,
                separator="\n\n",
                backup_separators=["\n", ".", "\u200B"],
            ),
            run_embedding_in_thread=self.run_embedding_in_thread,
            Source=self.Source,
            Index=self.Index,
            VS=self.VS,
            DS=self.DS,
            FSPath=self.FSPath,
            user_id=self.user_id,
            private=self.private,
            embedding=self.embedding,
        )

        return pipeline

    def run(
        self, file_paths: str | Path | list[str | Path], *args, **kwargs
    ) -> tuple[list[str | None], list[str | None]]:
        raise NotImplementedError

    def stream(
        self, file_paths: str | Path | list[str | Path], reindex: bool = False, **kwargs
    ) -> Generator[
        Document, None, tuple[list[str | None], list[str | None], list[Document]]
    ]:
        """Return a list of indexed file ids, and a list of errors"""
        if not isinstance(file_paths, list):
            file_paths = [file_paths]

        file_ids: list[str | None] = []
        errors: list[str | None] = []
        all_docs = []

        n_files = len(file_paths)
        for idx, file_path in enumerate(file_paths):
            if self.is_url(file_path):
                file_name = file_path
            else:
                file_path = Path(file_path)
                file_name = file_path.name

            yield Document(
                content=f"Indexing [{idx + 1}/{n_files}]: {file_name}",
                channel="debug",
            )

            try:
                pipeline = self.route(file_path)
                file_id, docs = yield from pipeline.stream(
                    file_path, reindex=reindex, **kwargs
                )
                all_docs.extend(docs)
                file_ids.append(file_id)
                errors.append(None)
                yield Document(
                    content={
                        "file_path": file_path,
                        "file_name": file_name,
                        "status": "success",
                    },
                    channel="index",
                )
            except Exception as e:
                logger.exception(e)
                file_ids.append(None)
                errors.append(str(e))
                yield Document(
                    content={
                        "file_path": file_path,
                        "file_name": file_name,
                        "status": "failed",
                        "message": str(e),
                    },
                    channel="index",
                )

        return file_ids, errors, all_docs
