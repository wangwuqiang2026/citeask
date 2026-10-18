"""Local lexical reranker: no model, no network, no download.

Why this exists: the shipped default reranker is Cohere, and without an API key it
returns the list unchanged — configured, reported as "on", and doing nothing (the
``doctor`` check flags exactly that). A cross-encoder would be the better answer, but
``fastembed`` 0.4.2 has no ``TextCrossEncoder`` and the model download is not
available on this host, so the honest first step is a reranker that needs nothing:
score the overlap between the question and each chunk with character n-grams (which
works for Chinese without a tokenizer) and keep the retrieval similarity untouched.

Two deliberate design points:

* the original ``score`` is preserved and the lexical score goes to
  ``metadata["rerank_score"]`` — the refusal gate is calibrated on retrieval
  similarity (MODIFICATIONS §5.8), and a reranker that rewrote scores would silently
  invalidate that threshold;
* the result is a *reordering*, not a filter, unless ``min_coverage`` is set: dropping
  documents is how a reranker turns a recoverable miss into a permanent one.
"""

from __future__ import annotations

import re
from typing import Iterable

from kotaemon.base import Document, Param

from .base import BaseReranking

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
_WORD = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Terms used for the overlap: CJK character bigrams + latin/digit words.

    Character bigrams are what makes this usable for Chinese without a segmenter
    ("加分细则" → 加分/分细/细则); unigrams are added for single-character queries.
    """
    lowered = (text or "").lower()
    terms: list[str] = []
    for run in _CJK.findall(lowered):
        if len(run) == 1:
            terms.append(run)
        terms.extend(run[index : index + 2] for index in range(len(run) - 1))
    terms.extend(word for word in _WORD.findall(lowered) if len(word) > 1)
    return terms


def lexical_score(query_terms: Iterable[str], document: str) -> float:
    """Share of the query's terms present in the document (0.0 – 1.0).

    Presence rather than frequency: the questions are short, so a repeated term says
    little about relevance, while "how much of the question is covered" is exactly
    what a reranker needs to order candidates. A fully covered question scores 1.0.
    """
    unique_terms = set(query_terms)
    if not unique_terms:
        return 0.0

    doc_terms = set(tokenize(document))
    if not doc_terms:
        return 0.0

    matched = len(unique_terms & doc_terms)
    return matched / len(unique_terms)


class LocalLexicalReranker(BaseReranking):
    """Reorder retrieved chunks by lexical overlap with the question."""

    min_coverage: float = Param(
        0.0,
        help=(
            "Drop documents whose overlap is below this (0 = keep every document and "
            "only reorder; filtering is what turns a miss into a permanent miss)"
        ),
    )
    top_k: int = Param(
        0,
        help="Keep at most this many documents after reordering (0 = keep all)",
    )

    def run(self, documents: list[Document], query: str) -> list[Document]:
        query_terms = tokenize(query)
        scored = []
        for document in documents:
            score = lexical_score(query_terms, document.text or "")
            document.metadata["rerank_score"] = round(score, 4)
            scored.append((score, document))

        # a stable sort: equal overlap keeps the retrieval order
        scored.sort(key=lambda item: item[0], reverse=True)
        ordered = [document for _, document in scored]

        if self.min_coverage > 0:
            ordered = [
                document
                for document in ordered
                if document.metadata.get("rerank_score", 0.0) >= self.min_coverage
            ]
        if self.top_k > 0:
            ordered = ordered[: self.top_k]
        return ordered
