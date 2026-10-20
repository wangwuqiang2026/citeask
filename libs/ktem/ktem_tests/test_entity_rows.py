"""Tests for the entity row lookup (``DocumentRetrievalPipeline._entity_row_docs``).

A question about one person is a *row* lookup: the chunk that carries the row has to
reach the context no matter what the vector ranking thinks of it. Measured on the
scholarship corpus (MODIFICATIONS §5.21): the rules notice scores 0.583 and the
student's standing row 0.351, so routing dropped both tables and the model answered
"cannot determine" although the row was in the index. The two filters that keep the
pass honest — a row *identifier* (a term that occupies a cell) and a cell match only —
are pinned here together with the promotion itself.
"""

from __future__ import annotations

from types import SimpleNamespace

from ktem.index.file import pipelines
from ktem.index.file.pipelines import DocumentRetrievalPipeline
from kotaemon.abstain import cell_names_entity, row_identifier_terms
from kotaemon.base import Document, RetrievedDocument

GRADE_ROW = "24405010134 赵明 62.5 71.43 66.965 39\n24405010135 张同学 75.45 84.27 79.86 4"
PRACTICE_ROW = "示例班级 24405010135 张同学 32 0 2025上半年16学时，2025下半年8学时"
COMPETITION_CELL = "10\n万物兴\n王丽丽\n马佳欣\n张同学\n二等奖+推荐省赛"
NOTICE_ROW = "一等奖学金:综合测评在班上前5名以内,各科成绩均为75分(含)以上"
NOTICE_PROSE = "三等奖学金:综合测评在班上前10名以内,各门功课考试成绩总分排名居班上前15名"
SUMMARY_HEADER = "学年：2025-2026学年 班级：示例班级 汇总人：王丽丽 联系方式：19164655656"


# --------------------------------------------------------------------------- #
# filter 1: the match has to be a cell
# --------------------------------------------------------------------------- #
def test_a_name_that_is_a_whole_cell_is_evidence():
    assert cell_names_entity(GRADE_ROW.splitlines()[1], "张同学") is True
    assert cell_names_entity(PRACTICE_ROW, "张同学") is True
    assert cell_names_entity("张同学", "张同学") is True


def test_a_window_inside_a_short_name_cell_is_evidence():
    """A 4-character name only ever reaches the question as 3-character windows."""
    row = "示例班级 24405010106 欧阳明月 28 4 2025上半年4学时"

    assert cell_names_entity(row, "欧阳明") is True
    assert cell_names_entity(row, "阳明月") is True


def test_a_window_of_a_topic_word_is_not_a_cell():
    """``等奖学`` is a window of ``三等奖学金``; the notice line is prose, not a cell."""
    assert cell_names_entity(NOTICE_ROW, "等奖学") is False
    assert cell_names_entity(NOTICE_PROSE, "三等奖") is False


def test_a_sentence_or_a_long_field_is_never_a_cell():
    assert cell_names_entity("一等奖学金的评定条件及相关说明", "等奖学") is False
    assert cell_names_entity(SUMMARY_HEADER, "王丽丽") is False


def test_a_too_short_window_is_not_evidence():
    """A window shorter than an entity (``王家`` for ``王家兴``) would match anything."""
    row = "示例班级 24405010132 王家兴 16 16"

    assert cell_names_entity(row, "王家兴") is True
    assert cell_names_entity(row, "王家") is False


def test_degenerate_cells_are_not_evidence():
    assert cell_names_entity("", "张同学") is False
    assert cell_names_entity(GRADE_ROW, "") is False
    assert cell_names_entity(GRADE_ROW, "王") is False
    # empty cells (padding only) are skipped, not treated as a match
    assert cell_names_entity("| | 张同学", "张同学") is True


# --------------------------------------------------------------------------- #
# filter 2: the term has to identify a row
# --------------------------------------------------------------------------- #
def test_a_name_that_occupies_rows_identifies_them():
    hits = [NOTICE_PROSE, GRADE_ROW, PRACTICE_ROW, COMPETITION_CELL]

    found = row_identifier_terms("张同学能评上校级三等奖学金吗", hits)

    assert found == {"张同学"}


def test_topic_words_are_not_identifiers():
    """``奖学金`` is prose; ``三等奖`` is an award column that repeats down a chunk."""
    award_column = "\n".join("三等奖" for _ in range(10))
    hits = [NOTICE_PROSE, NOTICE_ROW, award_column]

    found = row_identifier_terms("校级三等奖学金的评定条件是什么", hits)

    assert "奖学金" not in found
    assert "三等奖" not in found
    assert found == set()


def test_a_name_mentioned_in_prose_many_times_still_identifies_its_row():
    """The class's 汇总人 is named in headers and lists; her row is still hers.

    Counting how many chunks *mention* a term missed exactly this case (measured: a
    student in five chunks stopped being a row identifier, MODIFICATIONS §5.21).
    """
    hits = [
        SUMMARY_HEADER,
        SUMMARY_HEADER,
        PRACTICE_ROW.replace("张同学", "王丽丽"),
        GRADE_ROW.replace("张同学", "王丽丽"),
        COMPETITION_CELL,
    ]

    found = row_identifier_terms("王丽丽的综测排名是多少", hits)

    assert "王丽丽" in found


def test_a_team_name_is_a_row_identifier():
    found = row_identifier_terms("万物兴队获得了几等奖", [COMPETITION_CELL])

    assert "万物兴" in found


def test_identifier_terms_need_a_question_and_documents():
    assert row_identifier_terms("", [GRADE_ROW]) == set()
    assert row_identifier_terms("张同学", []) == set()


def test_one_character_terms_never_identify_a_row():
    """``加5分`` yields ``加``/``分``; a single character matches almost every chunk."""
    assert row_identifier_terms("加5分", [GRADE_ROW, PRACTICE_ROW]) == set()


def test_the_chunk_cap_is_optional():
    hits = [GRADE_ROW, PRACTICE_ROW, COMPETITION_CELL]

    assert "张同学" in row_identifier_terms("张同学的综测是多少", hits)
    assert "张同学" not in row_identifier_terms("张同学的综测是多少", hits, max_chunks=1)


def test_the_repetition_bar_can_be_stricter_or_looser():
    repeated = "\n".join(["张同学"] * 3)

    assert "张同学" not in row_identifier_terms("张同学的综测是多少", [repeated])
    assert "张同学" in row_identifier_terms(
        "张同学的综测是多少", [repeated], max_cell_repeats=3
    )


# --------------------------------------------------------------------------- #
# the lookup itself
# --------------------------------------------------------------------------- #
class StubDocStore:
    """Returns the prepared hits, like the full-text channel would."""

    def __init__(self, hits):
        self.hits = list(hits)
        self.queries = []

    def query(self, text, top_k=30, **kwargs):
        self.queries.append(text)
        return self.hits[:top_k]


def hit(file_id, text, name=None):
    return Document(
        text=text,
        metadata={"file_id": file_id, "file_name": name or f"{file_id}.xlsx"},
    )


def retriever_with(hits, retrieval_mode="hybrid"):
    return SimpleNamespace(DS=StubDocStore(hits), retrieval_mode=retrieval_mode)


def lookup(question, hits, selection, in_scope=None, retrieval_mode="hybrid"):
    self = retriever_with(hits, retrieval_mode=retrieval_mode)
    return DocumentRetrievalPipeline._entity_row_docs(
        self, question, selection, in_scope if in_scope is not None else selection
    )


def test_the_row_of_the_queried_person_is_promoted():
    """One chunk per file: the grade row and the practice row, not the notice prose."""
    hits = [
        hit("notice", NOTICE_PROSE),
        hit("grades", GRADE_ROW),
        hit("practice", PRACTICE_ROW),
        hit("competition", COMPETITION_CELL),
    ]

    picked = lookup(
        "张同学能评上校级三等奖学金吗",
        hits,
        ["notice", "grades", "practice", "competition"],
    )

    assert [doc.metadata["file_id"] for doc in picked] == [
        "grades",
        "practice",
        "competition",
    ]
    # a promoted chunk carries no similarity: the refusal gate judges the vector matches
    assert all(doc.score < 0 for doc in picked)


def test_the_pass_reaches_a_file_that_routing_dropped():
    """Routing kept ``notice``; the row lives in a file it dropped: the whole point."""
    hits = [hit("notice", NOTICE_PROSE), hit("grades", GRADE_ROW)]

    picked = lookup(
        "张同学能评上校级三等奖学金吗",
        hits,
        ["notice", "grades"],
        in_scope=["notice"],
    )

    assert [doc.metadata["file_id"] for doc in picked] == ["grades"]


def test_files_outside_the_users_selection_are_never_read():
    hits = [hit("grades", GRADE_ROW)]

    picked = lookup("张同学能评上校级三等奖学金吗", hits, ["notice"])

    assert picked == []


def test_a_question_without_a_name_promotes_nothing():
    """``图书馆``/``加分`` are not row identifiers: the pass must stay out of the way."""
    hits = [hit("points", NOTICE_PROSE), hit("grades", GRADE_ROW)]

    assert lookup("图书馆一次最多可以借几本书？", hits, ["points", "grades"]) == []


def test_prose_that_merely_contains_the_word_promotes_nothing():
    hits = [hit("notice", NOTICE_ROW)]

    assert lookup("一等奖学金的综测要求是什么", hits, ["notice"]) == []


def test_at_most_one_chunk_per_file():
    hits = [hit("grades", GRADE_ROW), hit("grades", PRACTICE_ROW)]

    picked = lookup("张同学的综测是多少", hits, ["grades"])

    assert len(picked) == 1


def test_the_number_of_promoted_chunks_is_capped(monkeypatch):
    monkeypatch.setattr(pipelines.settings, "KH_ENTITY_ROWS", 1)
    hits = [hit("grades", GRADE_ROW), hit("practice", PRACTICE_ROW)]

    picked = lookup("张同学的综测是多少", hits, ["grades", "practice"])

    assert len(picked) == 1


def test_the_pass_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(pipelines.settings, "KH_ENTITY_ROWS", 0)
    hits = [hit("grades", GRADE_ROW)]

    assert lookup("张同学的综测是多少", hits, ["grades"]) == []


def test_vector_only_retrieval_does_not_secretly_use_the_full_text_index():
    hits = [hit("grades", GRADE_ROW)]

    assert lookup("张同学的综测是多少", hits, ["grades"], retrieval_mode="vector") == []


def test_a_broken_docstore_does_not_break_retrieval():
    self = SimpleNamespace(
        DS=SimpleNamespace(query=lambda *a, **k: (_ for _ in ()).throw(RuntimeError())),
        retrieval_mode="hybrid",
    )

    assert (
        DocumentRetrievalPipeline._entity_row_docs(
            self, "张同学的综测是多少", ["grades"], ["grades"]
        )
        == []
    )


# --------------------------------------------------------------------------- #
# promotion into the context
# --------------------------------------------------------------------------- #
def retrieved(doc_id, score):
    return RetrievedDocument(text=doc_id, metadata={"file_id": doc_id}, score=score)


def test_promoted_rows_come_first():
    ranked = [retrieved("notice", 0.49), retrieved("grades", 0.35)]
    row = retrieved("grades", -1.0)
    row.doc_id = ranked[1].doc_id

    merged = DocumentRetrievalPipeline._promote_entity_rows(ranked, [row])

    # The chunk retrieval already returned keeps its identity and its score: a
    # promoted row replaced it with the NO_SIMILARITY copy, so the only score above
    # the abstain floor disappeared and the question was refused (§5.37).
    assert merged[0] is ranked[1]
    assert merged[0].score == 0.35
    assert merged[0].metadata["entity_row"] is True
    assert [doc.metadata["file_id"] for doc in merged] == ["grades", "notice"]


def test_a_row_chunk_retrieval_did_not_return_keeps_the_no_similarity_marker():
    ranked = [retrieved("notice", 0.49)]
    row = retrieved("grades", -1.0)

    merged = DocumentRetrievalPipeline._promote_entity_rows(ranked, [row])

    assert merged[0] is row
    assert merged[0].score == -1.0


def test_a_chunk_that_is_already_in_the_context_is_not_duplicated():
    ranked = [retrieved("grades", 0.35), retrieved("notice", 0.49)]
    row = retrieved("grades", -1.0)
    row.doc_id = ranked[0].doc_id

    merged = DocumentRetrievalPipeline._promote_entity_rows(ranked, [row])

    assert len(merged) == 2
    assert merged[0] is ranked[0]
    assert merged[0].score == 0.35


def test_without_rows_the_ranking_is_untouched():
    ranked = [retrieved("a", 0.4), retrieved("b", 0.3)]

    assert DocumentRetrievalPipeline._promote_entity_rows(ranked, []) == ranked
