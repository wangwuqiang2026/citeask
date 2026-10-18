"""File-level routing: remember what each file is about, so a question need not search
every file.

Retrieval used to run one vector query over the whole selection. With a 10k-chunk
spreadsheet in the corpus that is both slow and lossy (MODIFICATIONS §5.13): the small
table that holds the answer never makes the candidate list. Indexing now stores a short
profile of each file (``Source.note["summary"]``), and a question is routed to the few
files whose profile is closest to it — one extra *cached* embedding query instead of a
search over everything.

The profile is deterministic (file name + first/middle/last excerpt of the extracted
text), so indexing stays free of extra model calls and the profile can be rebuilt.
"""

from __future__ import annotations

import math

from typing import Iterable, Mapping

#: Characters taken from each excerpt of the file.
EXCERPT_CHARS = 400
#: How many excerpts (first / middle / last chunk) describe a file.
EXCERPTS = 3
#: Hard cap of the stored profile, so one huge file cannot bloat the database row.
MAX_PROFILE_CHARS = 2000


def build_file_profile(file_name: str, chunks: Iterable[str]) -> str:
    """A short, deterministic description of a file: name plus sample excerpts.

    Sampling instead of summarising with a model keeps indexing free and reproducible;
    the excerpts are enough to tell "积分细则" from "社会实践完成情况表" at query time.
    """
    texts = [str(chunk).strip() for chunk in chunks if chunk and str(chunk).strip()]
    picks: list[str] = []
    if texts:
        if len(texts) >= EXCERPTS:
            step = len(texts) // EXCERPTS
            picks = [texts[0], texts[min(step, len(texts) - 1)], texts[-1]]
        else:
            picks = texts

    body = " ".join(pick[:EXCERPT_CHARS] for pick in picks)
    profile = f"文件：{file_name}"
    if body:
        profile += f"\n内容摘录：{body}"
    return profile[:MAX_PROFILE_CHARS]


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    """Cosine of two vectors; 0.0 for malformed input, so routing degrades safely."""
    try:
        left_values = [float(value) for value in left]
        right_values = [float(value) for value in right]
    except (TypeError, ValueError):
        return 0.0
    if not left_values or len(left_values) != len(right_values):
        return 0.0

    dot = sum(a * b for a, b in zip(left_values, right_values))
    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def rank_files(
    question_vector: Iterable[float],
    profile_vectors: Mapping[str, Iterable[float]],
    top_m: int = 3,
    min_similarity: float = 0.30,
    min_ratio: float = 0.80,
    min_files: int = 2,
) -> list[str]:
    """File ids whose profile is closest to the question, best first.

    An empty list means "do not route": either nothing is close enough
    (``min_similarity``) or there is nothing to rank. Callers then search everything,
    which is the old behaviour and the safe default.

    Narrowing uses a **relative** cut (``min_ratio`` of the best score) rather than only
    a fixed ``top_m``: a question that names a row of one table scores 0.58 against that
    table and 0.40 against the rest, so it is routed to the table alone, while an
    ambiguous question keeps its near-ties. ``min_files`` keeps at least two files (when
    that many are available) so one word of overlap cannot hide the answer.
    """
    scored = [
        (file_id, cosine_similarity(question_vector, vector))
        for file_id, vector in profile_vectors.items()
    ]
    scored = [(file_id, score) for file_id, score in scored if score >= min_similarity]
    if not scored:
        return []

    scored.sort(key=lambda item: item[1], reverse=True)
    best = scored[0][1]
    cap = max(int(top_m), 1)
    floor = min(max(int(min_files), 1), cap)
    kept = [
        file_id for file_id, score in scored
        if score >= best * max(min_ratio, 0.0)
    ][:cap]

    for file_id, _ in scored:
        if len(kept) >= floor:
            break
        if file_id not in kept:
            kept.append(file_id)
    return kept


def profile_cache_key(file_id: str, profile: str) -> str:
    """Cache key of a profile embedding; a changed profile changes the key."""
    import hashlib

    digest = hashlib.sha1(profile.encode("utf-8")).hexdigest()[:16]
    return f"{file_id}:{digest}"


def entity_evidence_files(
    question: str,
    hits: Iterable[tuple[str, str]],
    allowed: Iterable[str],
    max_files: int = 2,
) -> list[str]:
    """Files among ``allowed`` whose chunk *names* the question's entity in a table.

    A profile says what a file is *about*; it cannot say who is *in* it. A spreadsheet of
    grades reads as a wall of numbers, so its profile is far from a natural question and
    the relative cut drops it — even when its rows contain the queried name
    (MODIFICATIONS §5.20). This is the missing signal: the file index's full-text channel
    already knows which chunks contain the entity, so the files carrying that evidence are
    kept in scope regardless of their profile.

    ``hits`` are ``(file id, chunk text)`` pairs from a full-text query over the whole
    index; ``allowed`` is the user's selection (the hits are filtered to it, so this never
    widens the search to files the user did not pick).
    """
    from kotaemon.abstain import text_names_entity

    allowed_ids = {str(file_id) for file_id in allowed or []}
    if not allowed_ids:
        return []

    matches: dict[str, int] = {}
    for file_id, text in hits or []:
        key = str(file_id)
        if key not in allowed_ids:
            continue
        if text_names_entity(question, text):
            matches[key] = matches.get(key, 0) + 1

    ordered = sorted(matches.items(), key=lambda item: (-item[1], item[0]))
    return [file_id for file_id, _ in ordered[: max(int(max_files), 0)]]


def add_entity_files(
    routed: Iterable[str], extra: Iterable[str], max_files: int = 8
) -> list[str]:
    """Union of the profile-routed files and the entity-evidence files, order kept."""
    ordered = [str(file_id) for file_id in routed or []]
    ordered += [str(file_id) for file_id in extra or []]
    cap = max(int(max_files), 1)
    return list(dict.fromkeys(ordered))[:cap]
