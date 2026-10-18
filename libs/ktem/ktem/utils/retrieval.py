"""Post-retrieval shaping shared by the file retrievers.

A single vector query ranks by similarity across the *whole* index, so one large file
can take every slot: with a 10k-chunk spreadsheet in the corpus, a 6-chunk table scores
0.34-0.41 (dense rows embed far from prose) and never makes the top-10 — the answer is
in the corpus but not in the context (MODIFICATIONS §5.13).

These helpers keep the strongest chunk of every file in the context before the second
chunk of any file, which is the cheapest fix: no extra embedding request, no extra
model, and it degrades to plain top-k when only one file is in scope.
"""

from __future__ import annotations

from typing import Any, Iterable


def source_key(document: Any) -> str:
    """Grouping key of a retrieved document: the file it came from.

    ``file_id`` is what the file index stores; ``file_name`` is the fallback for
    documents that predate it. Everything without either key is one group, which keeps
    the behaviour unchanged for other index types.
    """
    metadata = getattr(document, "metadata", None) or {}
    for key in ("file_id", "file_name"):
        value = metadata.get(key)
        if value:
            return str(value)
    return ""


def absent_source_ids(documents: Iterable[Any], file_ids: Iterable[str]) -> list[str]:
    """Selected files that the ranking did not represent at all, in selection order.

    These are the files worth an extra query: a dense table can be absent from a top-30
    list even though it holds the answer (MODIFICATIONS §5.13).
    """
    seen = {source_key(document) for document in documents}
    return [
        str(file_id)
        for file_id in file_ids or []
        if file_id is not None and str(file_id) not in seen
    ]


def diversify_by_source(
    documents: Iterable[Any],
    top_k: int,
    per_source_k: int | None = None,
) -> list[Any]:
    """Take the best chunk of each file, then the second best of each, and so on.

    The input order is preserved inside a group (the retriever already ordered it), and
    files are visited in the order of their best chunk, so the result stays a ranking —
    it is not a flat round-robin. ``per_source_k`` caps how many chunks a single file
    may contribute (``None`` = no cap).
    """
    if top_k <= 0:
        return []

    groups: dict[str, list[Any]] = {}
    order: list[str] = []
    for document in documents:
        key = source_key(document)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(document)

    if len(order) <= 1:
        return list(documents)[:top_k]

    picked: list[Any] = []
    round_index = 0
    while len(picked) < top_k:
        added = False
        for key in order:
            if len(picked) >= top_k:
                break
            bucket = groups[key]
            if round_index >= len(bucket):
                continue
            if per_source_k is not None and round_index >= per_source_k:
                continue
            picked.append(bucket[round_index])
            added = True
        if not added:
            break
        round_index += 1
    return picked
