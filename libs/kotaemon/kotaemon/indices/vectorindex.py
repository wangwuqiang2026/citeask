from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Optional, Sequence, cast

from theflow.settings import settings as flowsettings

from kotaemon.base import BaseComponent, Document, RetrievedDocument
from kotaemon.embeddings import BaseEmbeddings
from kotaemon.storages import BaseDocumentStore, BaseVectorStore

from .base import BaseIndexing, BaseRetrieval
from .rankings import BaseReranking, LLMReranking

VECTOR_STORE_FNAME = "vectorstore"
DOC_STORE_FNAME = "docstore"


class VectorIndexing(BaseIndexing):
    """Ingest the document, run through the embedding, and store the embedding in a
    vector store.

    This pipeline supports the following set of inputs:
        - List of documents
        - List of texts
    """

    cache_dir: Optional[str] = getattr(flowsettings, "KH_CHUNKS_OUTPUT_DIR", None)
    vector_store: BaseVectorStore
    doc_store: Optional[BaseDocumentStore] = None
    embedding: BaseEmbeddings
    count_: int = 0

    def to_retrieval_pipeline(self, *args, **kwargs):
        """Convert the indexing pipeline to a retrieval pipeline"""
        return VectorRetrieval(
            vector_store=self.vector_store,
            doc_store=self.doc_store,
            embedding=self.embedding,
            **kwargs,
        )

    def write_chunk_to_file(self, docs: list[Document]):
        # save the chunks content into markdown format
        if self.cache_dir:
            file_name = docs[0].metadata.get("file_name")
            if not file_name:
                return

            file_name = Path(file_name)
            for i in range(len(docs)):
                markdown_content = ""
                if "page_label" in docs[i].metadata:
                    page_label = str(docs[i].metadata["page_label"])
                    markdown_content += f"Page label: {page_label}"
                if "file_name" in docs[i].metadata:
                    filename = docs[i].metadata["file_name"]
                    markdown_content += f"\nFile name: {filename}"
                if "section" in docs[i].metadata:
                    section = docs[i].metadata["section"]
                    markdown_content += f"\nSection: {section}"
                if "type" in docs[i].metadata:
                    if docs[i].metadata["type"] == "image":
                        image_origin = docs[i].metadata["image_origin"]
                        image_origin = f'<p><img src="{image_origin}"></p>'
                        markdown_content += f"\nImage origin: {image_origin}"
                if docs[i].text:
                    markdown_content += f"\ntext:\n{docs[i].text}"

                with open(
                    Path(self.cache_dir) / f"{file_name.stem}_{self.count_+i}.md",
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(markdown_content)

    def add_to_docstore(self, docs: list[Document]):
        if self.doc_store:
            print("Adding documents to doc store")
            self.doc_store.add(docs)

    def add_to_vectorstore(self, docs: list[Document]):
        # in case we want to skip embedding
        if self.vector_store:
            print(f"Getting embeddings for {len(docs)} nodes")
            embeddings = self.embedding(docs)
            print("Adding embeddings to vector store")
            self.vector_store.add(
                embeddings=embeddings,
                ids=[t.doc_id for t in docs],
            )

    def run(self, text: str | list[str] | Document | list[Document]):
        input_: list[Document] = []
        if not isinstance(text, list):
            text = [text]

        for item in cast(list, text):
            if isinstance(item, str):
                input_.append(Document(text=item, id_=str(uuid.uuid4())))
            elif isinstance(item, Document):
                input_.append(item)
            else:
                raise ValueError(
                    f"Invalid input type {type(item)}, should be str or Document"
                )

        self.add_to_vectorstore(input_)
        self.add_to_docstore(input_)
        self.write_chunk_to_file(input_)
        self.count_ += len(input_)


def limit_keyword_only(
    documents: list["RetrievedDocument"], budget: int
) -> list["RetrievedDocument"]:
    """Keep at most ``budget`` keyword-only (score < 0) documents.

    Once the full-text index matched Chinese, keyword hits could fill the whole result
    list. They carry no similarity (the ``-1`` sentinel), so the refusal gate lost its
    only signal and answered everything (MODIFICATIONS §5.15). Reserving slots for
    similarity-ranked documents keeps the gate measurable without dropping the keyword
    hits that make exact-name lookups work.
    """
    budget = max(int(budget), 1)
    kept: list["RetrievedDocument"] = []
    keyword_only = 0
    for document in documents:
        try:
            score = float(getattr(document, "score", 0.0) or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if score < 0:
            if keyword_only >= budget:
                continue
            keyword_only += 1
        kept.append(document)
    return kept


def similarity_documents_first(
    documents: list["RetrievedDocument"],
) -> list["RetrievedDocument"]:
    """Similarity-scored documents first, keyword-only hits (score < 0) after them.

    A keyword hit has no similarity, so it cannot be compared with a vector match - which
    is why it was placed in front of the list. Once the full-text index started returning
    hits for a *scoped* query (MODIFICATIONS §5.19), that order pushed the best chunks out
    of the context: on the 27-question set the best score fell by 0.2-0.3 for two thirds
    of the questions and 16 of them were refused, although the answer chunk had been
    ranked first before. Ordering them last keeps the exact-name safety net (they still
    fill the slots the similarity ranking left over) without demoting real matches.
    """
    scored: list["RetrievedDocument"] = []
    keyword_only: list["RetrievedDocument"] = []
    for document in documents:
        try:
            score = float(getattr(document, "score", 0.0) or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        (keyword_only if score < 0 else scored).append(document)
    return scored + keyword_only


class VectorRetrieval(BaseRetrieval):
    """Retrieve list of documents from vector store"""

    vector_store: BaseVectorStore
    doc_store: Optional[BaseDocumentStore] = None
    embedding: BaseEmbeddings
    rerankers: Sequence[BaseReranking] = []
    top_k: int = 5
    first_round_top_k_mult: int = 10
    retrieval_mode: str = "hybrid"  # vector, text, hybrid

    def _filter_docs(
        self, documents: list[RetrievedDocument], top_k: int | None = None
    ):
        if top_k:
            documents = documents[:top_k]
        return documents

    def run(
        self, text: str | Document, top_k: Optional[int] = None, **kwargs
    ) -> list[RetrievedDocument]:
        """Retrieve a list of documents from vector store

        Args:
            text: the text to retrieve similar documents
            top_k: number of top similar documents to return

        Returns:
            list[RetrievedDocument]: list of retrieved documents
        """
        if top_k is None:
            top_k = self.top_k

        do_extend = kwargs.pop("do_extend", False)
        thumbnail_count = kwargs.pop("thumbnail_count", 3)
        # consumed below; it must not reach the vector store query
        keyword_slots = kwargs.pop("keyword_slots", None)
        # Only a handful of keyword hits reach the context, and every candidate is
        # tokenized by the reranker, so asking the full-text index for hundreds is pure
        # latency (300 long table rows made one retrieval take 3.2s).
        docstore_top_k = kwargs.pop("docstore_top_k", None)

        if do_extend:
            top_k_first_round = top_k * self.first_round_top_k_mult
        else:
            top_k_first_round = top_k
        if docstore_top_k is None:
            docstore_top_k = top_k_first_round

        if self.doc_store is None:
            raise ValueError(
                "doc_store is not provided. Please provide a doc_store to "
                "retrieve the documents"
            )

        result: list[RetrievedDocument] = []
        # TODO: should declare scope directly in the run params
        scope = kwargs.pop("scope", None)
        # A caller that runs several queries for the same question (the per-file pass in
        # ktem's file retriever) can embed the question once and hand the vector over;
        # embedding again per file doubled the retrieval latency (MODIFICATIONS §5.13).
        query_embedding = kwargs.pop("query_embedding", None)
        emb: list[float]

        if self.retrieval_mode == "vector":
            emb = query_embedding or self.embedding(text)[0].embedding
            _, scores, ids = self.vector_store.query(
                embedding=emb, top_k=top_k_first_round, doc_ids=scope, **kwargs
            )
            docs = self.doc_store.get(ids)
            result = [
                RetrievedDocument(**doc.to_dict(), score=score)
                for doc, score in zip(docs, scores)
            ]
        elif self.retrieval_mode == "text":
            query = text.text if isinstance(text, Document) else text
            docs = []
            if scope:
                docs = self.doc_store.query(
                    query, top_k=top_k_first_round, doc_ids=scope
                )
            result = [RetrievedDocument(**doc.to_dict(), score=-1.0) for doc in docs]
        elif self.retrieval_mode == "hybrid":
            # similarity search section
            emb = query_embedding or self.embedding(text)[0].embedding
            vs_docs: list[RetrievedDocument] = []
            vs_ids: list[str] = []
            vs_scores: list[float] = []

            def query_vectorstore():
                nonlocal vs_docs
                nonlocal vs_scores
                nonlocal vs_ids

                assert self.doc_store is not None
                _, vs_scores, vs_ids = self.vector_store.query(
                    embedding=emb, top_k=top_k_first_round, doc_ids=scope, **kwargs
                )
                if vs_ids:
                    vs_docs = self.doc_store.get(vs_ids)

            # full-text search section
            ds_docs: list[RetrievedDocument] = []

            def query_docstore():
                nonlocal ds_docs

                assert self.doc_store is not None
                query = text.text if isinstance(text, Document) else text
                if scope:
                    ds_docs = self.doc_store.query(
                        query, top_k=docstore_top_k, doc_ids=scope
                    )

            vs_query_thread = threading.Thread(target=query_vectorstore)
            ds_query_thread = threading.Thread(target=query_docstore)

            vs_query_thread.start()
            ds_query_thread.start()

            vs_query_thread.join()
            ds_query_thread.join()

            result = [
                RetrievedDocument(**doc.to_dict(), score=-1.0)
                for doc in ds_docs
                if doc not in vs_ids
            ]
            result += [
                RetrievedDocument(**doc.to_dict(), score=score)
                for doc, score in zip(vs_docs, vs_scores)
            ]
            print(f"Got {len(vs_docs)} from vectorstore")
            print(f"Got {len(ds_docs)} from docstore")

        # use additional reranker to re-order the document list
        if self.rerankers and text:
            for reranker in self.rerankers:
                # if reranker is LLMReranking, limit the document with top_k items only
                if isinstance(reranker, LLMReranking):
                    result = self._filter_docs(result, top_k=top_k)
                result = reranker.run(documents=result, query=text)

        # keyword-only hits must not crowd out every similarity-scored document, or the
        # refusal gate has nothing to judge (MODIFICATIONS §5.15). ``keyword_slots`` is
        # set by the caller, because it asks for more candidates than the context needs.
        if self.retrieval_mode == "hybrid":
            budget = (
                int(keyword_slots)
                if keyword_slots is not None
                else max(1, top_k // 2)
            )
            result = limit_keyword_only(result, budget)
            # ... and they must not outrank a real similarity match either (MODIFICATIONS
            # §5.19). Applied after the reranker, which floats an exact-name chunk up by
            # coverage and would otherwise re-create the same displacement.
            result = similarity_documents_first(result)

        result = self._filter_docs(result, top_k=top_k)
        print(f"Got raw {len(result)} retrieved documents")

        # add page thumbnails to the result if exists
        thumbnail_doc_ids: set[str] = set()
        # we should copy the text from retrieved text chunk
        # to the thumbnail to get relevant LLM score correctly
        text_thumbnail_docs: dict[str, RetrievedDocument] = {}

        non_thumbnail_docs = []
        raw_thumbnail_docs = []
        for doc in result:
            if doc.metadata.get("type") == "thumbnail":
                # change type to image to display on UI
                doc.metadata["type"] = "image"
                raw_thumbnail_docs.append(doc)
                continue
            if (
                "thumbnail_doc_id" in doc.metadata
                and len(thumbnail_doc_ids) < thumbnail_count
            ):
                thumbnail_id = doc.metadata["thumbnail_doc_id"]
                thumbnail_doc_ids.add(thumbnail_id)
                text_thumbnail_docs[thumbnail_id] = doc
            else:
                non_thumbnail_docs.append(doc)

        linked_thumbnail_docs = self.doc_store.get(list(thumbnail_doc_ids))
        print(
            "thumbnail docs",
            len(linked_thumbnail_docs),
            "non-thumbnail docs",
            len(non_thumbnail_docs),
            "raw-thumbnail docs",
            len(raw_thumbnail_docs),
        )
        additional_docs = []

        for thumbnail_doc in linked_thumbnail_docs:
            text_doc = text_thumbnail_docs[thumbnail_doc.doc_id]
            doc_dict = thumbnail_doc.to_dict()
            doc_dict["_id"] = text_doc.doc_id
            doc_dict["content"] = text_doc.content
            doc_dict["metadata"]["type"] = "image"
            for key in text_doc.metadata:
                if key not in doc_dict["metadata"]:
                    doc_dict["metadata"][key] = text_doc.metadata[key]

            additional_docs.append(RetrievedDocument(**doc_dict, score=text_doc.score))

        result = additional_docs + non_thumbnail_docs

        if not result:
            # return output from raw retrieved thumbnails
            result = self._filter_docs(raw_thumbnail_docs, top_k=thumbnail_count)

        return result


class TextVectorQA(BaseComponent):
    retrieving_pipeline: BaseRetrieval
    qa_pipeline: BaseComponent

    def run(self, question, **kwargs):
        retrieved_documents = self.retrieving_pipeline(question, **kwargs)
        return self.qa_pipeline(question, retrieved_documents, **kwargs)
