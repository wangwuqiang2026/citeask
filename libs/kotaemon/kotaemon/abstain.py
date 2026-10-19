"""Refusal gate: decide whether the retrieved evidence is strong enough to answer.

The chat page used to answer from the retrieved chunks whenever anything came back,
so a question the corpus cannot answer was answered anyway (from the model's own
memory or, worse, from an unrelated chunk). This gate makes that decision explicit
and shared: the retrieval evaluator (``tools/eval_retrieval.py``) scores exactly the
decision the chat pipeline makes, so the threshold quoted in the README is measured,
not estimated.

Two details matter for the calibration:

* the hybrid retriever marks documents found by *full-text* search with a negative
  sentinel score (see ``kotaemon/indices/vectorindex.py``), because there is no
  similarity for them. A negative score means "found by keyword", not "a bad match",
  so those lists are not refused — there is simply no similarity to judge;
* ``threshold <= 0`` disables the gate except for the "nothing retrieved" case,
  which is the behaviour before this module existed (a kill switch).

A single global threshold is calibrated on *prose*. A dense table (a spreadsheet with
one row per student) scores low even for the row that contains the queried name, because
the row is mostly digits; refusing those questions is wrong (MODIFICATIONS §5.8). So a
matched **rare entity term** - a verbatim 3-character CJK run such as a person's name,
or a 3+ character latin/digit token such as an ID - plus a lower floor keeps the
decision honest: never answer on a 0.18 match, but do not refuse a 0.38 match that names
the row.

A table is not always rendered as a row of fields. A PDF (or any loader that emits one
cell per line) turns the same row into ``10`` / ``星河队`` / ``李明辉`` / ``二等奖+推荐省赛``
lines, where no single line has "fields" at all and the row test above can never match.
The name standing alone on its line *is* the cell, so that layout counts as well
(MODIFICATIONS §5.19) - prose lines are far too long to ever be a whole cell.

Source code is the mirror image of a spreadsheet: it carries the answer, but a Chinese
question is far from Python identifiers in the vector space (0.34-0.39 against 0.45-0.62
for prose), so the prose threshold refuses questions about it. The structural signal
there is the **file name**: a question that names the file is answered from that file
down to the same floor (:func:`named_file_evidence`, MODIFICATIONS §5.22).

Two of these rules are shared with retrieval: :func:`row_identifier_terms` (which terms
of the question name a row rather than a topic) and :func:`cell_names_entity` (the
whole-cell match the file retriever uses when it promotes the row into the context,
MODIFICATIONS §5.21).
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

#: Score the hybrid retriever gives to full-text-only matches (no similarity).
NO_SIMILARITY = -1.0

#: How far below the threshold a *rare entity term* match may still count as evidence.
#: Calibrated on the spreadsheet corpus: the row that names the queried student scores
#: 0.34-0.38, while questions about absent entities stay at or below 0.32.
DEFAULT_TERM_FLOOR = 0.33

#: Shortest CJK run (and latin token) that reads as an entity rather than a common word.
ENTITY_TERM_LENGTH = 3

#: Longest CJK-only cell a 3-character window may match inside: a name/team cell is
#: short (``欧阳佳饴``), a sentence or a labelled field is not.
MAX_CELL_LENGTH = 6

#: How often a term may repeat inside one chunk and still read as a row value. An award
#: column (``三等奖`` ten times in one OCR chunk) repeats; a name appears once
#: (MODIFICATIONS §5.21).
MAX_CELL_REPEATS = 2

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_CJK_ONLY = re.compile(r"^[\u4e00-\u9fff]+$")
_LATIN_TOKEN = re.compile(r"[a-z0-9]+")
_FIELD_SPLIT = re.compile(r"[,\t]")
_HAS_DIGIT = re.compile(r"\d")

#: Padding a loader may leave around a cell when it emits one cell per line.
_CELL_PADDING = " \t\u3000:：,，、;；|"

#: Characters that mark a *sentence* rather than a table cell.
_SENTENCE_MARKS = "。，；：！？、,"


def best_similarity(scores: Iterable[float]) -> Optional[float]:
    """Best *similarity* score, ignoring keyword-only placeholder scores.

    Returns ``None`` when no document carries a similarity score at all.
    """
    usable = []
    for score in scores:
        try:
            value = float(score)
        except (TypeError, ValueError):
            continue
        if value > 0:
            usable.append(value)
    return max(usable) if usable else None


def entity_terms(question: str, length: int = ENTITY_TERM_LENGTH) -> set[str]:
    """Entity-like terms of a question: CJK windows and 3+ character latin tokens.

    ``李明辉的社会实践完成了吗`` yields ``李明辉``/``明辉的``/...; ``2025`` and student
    ids survive as-is. The windows overlap on purpose — the match only needs one.
    """
    terms: set[str] = set()
    for run in _CJK_RUN.findall(question or ""):
        if len(run) <= length:
            terms.add(run)
            continue
        for start in range(len(run) - length + 1):
            terms.add(run[start : start + length])
    for token in _LATIN_TOKEN.findall((question or "").lower()):
        if len(token) >= length:
            terms.add(token)
    return terms


def row_looks_tabular(line: str, min_numbered_share: float = 0.6) -> bool:
    """A spreadsheet row rather than a sentence: several fields, most of them numbered.

    The distinction matters because a *prose* sentence can mention the same noun without
    being able to answer a question about it: ``图书馆`` appears in the points-rules
    document ("在图书馆借阅…加 2 分"), but that sentence cannot say how many books may be
    borrowed. A row of ``24405010001 李明辉 8 24 2025上半年8学时`` can.
    """
    fields = [field for field in _FIELD_SPLIT.split(line) if field.strip()]
    if len(fields) < 3:
        fields = line.split()
    if len(fields) < 3:
        return False

    numbered = sum(1 for field in fields if _HAS_DIGIT.search(field))
    return numbered >= 2 and numbered / len(fields) >= min_numbered_share


def line_is_a_cell(line: str, term: str) -> bool:
    """True when ``term`` occupies a whole line, i.e. is one cell of a vertical table.

    A spreadsheet loader writes a row as one line with several fields, but a PDF/OCR
    loader writes one cell per line, so a row looks like::

        10
        星河队
        赵一鸣
        钱二毛
        李明辉
        二等奖+推荐省赛

    ``row_looks_tabular`` cannot match that layout (a single field is not a row), yet the
    name is still the exact row the question is about. An exact whole-line match is a
    high bar on purpose: a prose line is a sentence, never a three-character cell.
    """
    stripped = str(line or "").strip().strip(_CELL_PADDING)
    return bool(stripped) and stripped == term


def cell_names_entity(
    line: str, term: str, max_cell_length: int = MAX_CELL_LENGTH
) -> bool:
    """True when ``term`` sits in a cell: a whole field, or a window of a short one.

    The row-lookup pass needs a higher bar than :func:`text_names_entity`: a mismatch
    there puts a *wrong* chunk into the context, while routing merely widens the file
    scope. Two layouts must match:

    * a field of a row: ``24405010135 王务强 75.45 …`` splits into fields, one of which is
      the name;
    * a cell of a vertical table (one cell per line, as OCR emits it): the line itself.

    A field such as ``一等奖学金:综合测评在班上前5名以内`` is prose that merely contains the
    window ``等奖学`` of ``三等奖学金`` — punctuation disqualifies it. A 3-character window
    also has to match *inside* a longer but still short CJK cell, because the question
    ``欧阳佳饴的社会实践`` yields only ``欧阳佳``/``阳佳饴`` and never the whole name
    (MODIFICATIONS §5.21).
    """
    body = str(line or "").strip()
    needle = str(term or "").strip().lower()
    if not body or not needle:
        return False

    for field in re.split(r"[,\t\s\u3000]+", body):
        piece = field.strip(_CELL_PADDING)
        if not piece:
            continue
        if piece.lower() == needle:
            return True
        if (
            len(needle) >= ENTITY_TERM_LENGTH
            and len(piece) <= max_cell_length
            and _CJK_ONLY.match(piece)
            and needle in piece.lower()
        ):
            return True
    return False


def text_names_entity(
    question: str, text: str, max_cell_length: int = 20, min_term_length: int = 3
) -> bool:
    """True when an entity term of the question sits in a table cell/row of ``text``.

    Weaker than :func:`specific_term_evidence` on purpose, and used by a different
    decision: **file routing** (MODIFICATIONS §5.20), not the answer gate. Rule: an entity
    term occurs in a line that is a numbered row (:func:`row_looks_tabular`) or a short
    standalone cell — where "cell" means an exact cell *or* a cell that merely contains
    the term, because a name is split into 3-character windows (``李明`` inside ``李明辉``).

    ``min_term_length`` drops the one-character runs :func:`entity_terms` returns for a
    short CJK run: ``一、二、三等奖`` and ``加5分`` yield the terms ``二``/``三``/``分``,
    which match a cell in almost every table and dragged unrelated files into the search
    scope (measured: 2 of 27 answerable questions lost their key facts that way).

    The weakness is fine for routing (the most it does is put a file into the search
    scope, and the gate still judges the evidence) but it is **not** fine for the gate:
    a short prose line such as ``在图书馆借阅`` would pass here and turn a "cannot answer"
    question into an answer. Keep the two rules separate.
    """
    body = str(text or "").lower()
    terms = {term for term in entity_terms(question) if len(term) >= min_term_length}
    if not body or not terms:
        return False

    for line in body.splitlines():
        if not any(term in line for term in terms):
            continue
        if row_looks_tabular(line):
            return True
        stripped = line.strip()
        if (
            stripped
            and len(stripped) <= max_cell_length
            and not any(mark in stripped for mark in _SENTENCE_MARKS)
        ):
            return True
    return False


def _text_of(item) -> str:
    """Text of a document or of a plain string, lowercased (empty for anything else)."""
    raw = item if isinstance(item, str) else getattr(item, "text", "")
    return str(raw or "").lower()


def row_identifier_terms(
    question: str,
    documents: Iterable,
    max_chunks: int = 0,
    max_cell_repeats: int = MAX_CELL_REPEATS,
) -> set[str]:
    """Terms of the question that name a *row*, not a topic.

    A row lookup needs the term that identifies the row. Judging that on "how often the
    term appears in the full-text hits" is fragile in both directions (MODIFICATIONS
    §5.21): a student who is also the class's 汇总人 appears in five chunks and stopped
    counting, while ``三等奖`` appears in seven and kept counting. What separates them is
    *how* the term appears:

    * a row identifier occupies a **cell** (:func:`cell_names_entity`), once or twice
      per chunk — ``24405010135 王务强 75.45 …``, ``万物兴`` on its own line;
    * a topic word is prose (``奖学金`` inside a sentence) or a **column value** that
      repeats down the chunk (``三等奖`` ten times in one OCR chunk).

    ``max_cell_repeats`` is the repetition bar; ``max_chunks`` is an optional cap on
    how many chunks may carry the cell (``0`` = no cap: a student who appears in ten
    tables is still a row identifier, and the caller caps how many of them it promotes).

    ``documents`` may be documents or plain strings.
    """
    texts = [text for text in (_text_of(item) for item in documents) if text]
    if not texts:
        return set()

    cap = max(int(max_chunks), 0)
    repeats_cap = max(int(max_cell_repeats), 1)
    found: set[str] = set()
    for term in entity_terms(question):
        if len(term) < ENTITY_TERM_LENGTH:
            continue
        chunks = 0
        worst = 0
        for text in texts:
            repeats = sum(
                1 for line in text.splitlines() if cell_names_entity(line, term)
            )
            if repeats:
                chunks += 1
                worst = max(worst, repeats)
        if not chunks or worst > repeats_cap:
            continue
        if cap and chunks > cap:
            continue
        found.add(term)
    return found


def specific_term_evidence(
    question: str,
    documents: Iterable,
    max_document_share: float = 0.3,
    require_tabular: bool = True,
) -> bool:
    """True when a *rare* entity term of the question appears in a table cell.

    "Rare" is judged on the retrieved list: a term found in most of the chunks is a
    topic word (``加分细则``), not evidence about a specific row. "Tabular" keeps prose
    matches out, where the noun is mentioned but the answer is elsewhere; a cell is a
    line of one row of fields, or (a vertical table) the term alone on its line.
    """
    texts = [str(getattr(document, "text", "") or "").lower() for document in documents]
    texts = [text for text in texts if text]
    terms = entity_terms(question)
    if not texts or not terms:
        return False

    max_matches = max(2, int(len(texts) * max_document_share))
    for term in terms:
        matches = 0
        hit = False
        for text in texts:
            if term not in text:
                continue
            matches += 1
            if hit or not require_tabular:
                hit = True
                continue
            hit = any(
                term in line
                and (row_looks_tabular(line) or line_is_a_cell(line, term))
                for line in text.splitlines()
            )
        if hit and 0 < matches <= max_matches:
            return True
    return False


#: Shortest file stem that can be recognised inside a question ("代码" in 代码.txt).
MIN_NAMED_FILE_LENGTH = 2

_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,6}$")


def _squash(text: str) -> str:
    """Lowercase and drop everything but letters/digits (CJK counts as a letter)."""
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


def named_file_evidence(question: str, documents: Iterable) -> bool:
    """True when the question names a file that one of the retrieved chunks is from.

    A question about a *document* is answered by that document even when the similarity
    is low: source code against a Chinese question scores 0.34-0.39 while prose scores
    0.45-0.62, so the prose threshold refuses the very questions that named their source
    ("代码里用了什么算法" at 0.39, "代码文件夹描述了什么算法" at 0.35 — measured,
    MODIFICATIONS §5.22).

    The test is strict on purpose: the file's stem, with whitespace and punctuation
    removed, must appear in the question, so ``代码`` matches only a file called
    ``代码.txt`` and a long descriptive name never matches by accident.
    """
    normalized_question = _squash(question)
    if not normalized_question:
        return False

    for item in documents or []:
        metadata = getattr(item, "metadata", None) or {}
        name = metadata.get("file_name")
        if not name:
            continue
        stem = _squash(_EXTENSION.sub("", str(name)))
        if len(stem) >= MIN_NAMED_FILE_LENGTH and stem in normalized_question:
            return True
    return False


def should_refuse(
    scores: Iterable[float],
    threshold: float,
    documents: Optional[Iterable] = None,
    question: str = "",
    term_floor: Optional[float] = None,
) -> bool:
    """True when the answer should be refused for lack of evidence.

    Args:
        scores: one score per retrieved document (order does not matter)
        threshold: minimum similarity that counts as evidence; ``<= 0`` disables
            the similarity check
        documents: the retrieved documents; when given together with ``question``, a
            rare entity term in one of them — or a file the question names — lowers the
            bar to ``term_floor``
        question: the user's question, used for the entity-term / file-name checks
        term_floor: lowest similarity that still counts once the evidence is structural
    """
    scores = list(scores)
    if not scores:
        return True
    if threshold <= 0:
        return False
    best = best_similarity(scores)
    if best is None:
        return False
    if best >= threshold:
        return False

    floor = DEFAULT_TERM_FLOOR if term_floor is None else float(term_floor)
    if documents is not None and question and floor > 0 and best >= floor:
        retrieved = list(documents)
        if specific_term_evidence(question, retrieved):
            return False
        if named_file_evidence(question, retrieved):
            return False
    return True
