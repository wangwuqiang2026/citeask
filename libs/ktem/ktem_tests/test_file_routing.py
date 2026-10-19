"""Tests for file routing (``ktem.index.file.routing``).

Every indexed file keeps a short profile ("文件：… 内容摘录：…"), and a question is
routed to the few files whose profile is closest to it — so a question does not have to
search every file, and a small table is not crowded out by a large spreadsheet
(MODIFICATIONS §5.13/§5.14). The pure parts of that decision are pinned here.
"""

from __future__ import annotations

import math

import pytest

from ktem.index.file.routing import (
    MAX_PROFILE_CHARS,
    add_entity_files,
    build_file_profile,
    cosine_similarity,
    entity_evidence_files,
    profile_cache_key,
    rank_files,
)
from kotaemon.abstain import text_names_entity


def test_the_profile_names_the_file_and_samples_its_text():
    profile = build_file_profile(
        "积分细则.pdf", ["第一条 积分由五个部分组成", "第二条 加分标准", "第三条 减分"]
    )

    assert profile.startswith("文件：积分细则.pdf")
    assert "内容摘录：" in profile
    assert "第一条" in profile
    assert "第三条" in profile  # the last chunk is sampled too


def test_a_profile_of_an_empty_file_is_still_a_name():
    assert build_file_profile("空白.txt", []) == "文件：空白.txt"
    assert build_file_profile("空白.txt", ["", None]) == "文件：空白.txt"


def test_product_profiles_are_capped():
    chunks = ["很长的一段内容" * 500] * 3

    profile = build_file_profile("大文件.pdf", chunks)

    assert len(profile) <= MAX_PROFILE_CHARS
    # the excerpt itself is bounded, so the profile stays informative rather than huge
    assert profile.count("很长的一段内容") <= (MAX_PROFILE_CHARS // 7) + 1


def test_two_chunks_are_both_sampled():
    profile = build_file_profile("两张.png", ["第一页文字", "第二页文字"])

    assert "第一页文字" in profile and "第二页文字" in profile


def test_cosine_similarity_is_bounded_and_safe():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity(None, [1.0]) == 0.0
    # a zero vector has no direction: routing must treat it as "no signal", not crash
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_the_closest_files_are_ranked_first():
    vectors = {
        "points": [1.0, 0.0],
        "exam": [0.0, 1.0],
        "mixed": [0.7, 0.7],
    }

    ranked = rank_files([1.0, 0.0], vectors, top_m=2, min_similarity=0.1)

    assert ranked == ["points", "mixed"]


def test_nothing_close_enough_means_no_route():
    """An unrelated question must not be routed to a random file: search everything."""
    vectors = {"a": [0.0, 1.0], "b": [0.0, 1.0]}

    assert rank_files([1.0, 0.0], vectors, top_m=2, min_similarity=0.5) == []


def test_top_m_is_respected():
    vectors = {"a": [1.0, 0.0], "b": [0.9, 0.1], "c": [0.8, 0.2]}

    assert len(rank_files([1.0, 0.0], vectors, top_m=1, min_similarity=0.1)) == 1


def test_a_specific_question_is_routed_to_its_own_file():
    """0.58 for the table that names the row, 0.40 for the rest: route to the table."""

    def at(score):
        return [score, math.sqrt(max(1.0 - score * score, 0.0))]

    vectors = {"table": at(0.58), "pdf": at(0.40), "docx": at(0.35)}

    routed = rank_files(
        [1.0, 0.0], vectors, top_m=3, min_similarity=0.3, min_ratio=0.8, min_files=1
    )

    assert routed == ["table"]


def test_min_files_keeps_a_second_candidate_by_default():
    """One word of overlap must not hide the answer, so two files stay in scope."""

    def at(score):
        return [score, math.sqrt(max(1.0 - score * score, 0.0))]

    vectors = {"table": at(0.58), "pdf": at(0.40), "docx": at(0.35)}

    routed = rank_files([1.0, 0.0], vectors, top_m=3, min_similarity=0.3)

    assert routed == ["table", "pdf"]


def test_a_narrow_question_never_routes_to_more_than_top_m():
    vectors = {str(index): [1.0 - index * 0.01, 0.0] for index in range(5)}

    routed = rank_files([1.0, 0.0], vectors, top_m=2, min_similarity=0.3)

    assert len(routed) == 2


def test_equal_profiles_are_broken_by_file_id():
    """Equal profile similarity must route in the same order every run.

    The order decides which file the per-file pass visits first, so an unstable tie
    moves a measurement by one question (MODIFICATIONS §5.22).
    """
    vectors = {"b": [1.0, 0.0], "a": [1.0, 0.0]}

    assert rank_files([1.0, 0.0], vectors, top_m=2) == ["a", "b"]


def test_a_changed_profile_changes_the_cache_key():
    first = profile_cache_key("file-1", "文件：a")
    second = profile_cache_key("file-1", "文件：b")

    assert first != second
    assert first.startswith("file-1:")
    assert profile_cache_key("file-1", "文件：a") == first


# --------------------------------------------------------------------------- #
# entity evidence: a profile says what a file is about, not who is in it (§5.20)
# --------------------------------------------------------------------------- #
GRADE_ROW = "24405010002 顾晓东 65 75.7 70.35 23\n24405010001 李明辉 75.45 84.27 79.86 4"
PROSE = "第七条 在图书馆借阅思想政治类书籍，每学期每次加 2 分，最高不超过 10 分。"
COMPETITION = "10\n星河队\n赵一鸣\n钱二毛\n李明辉\n二等奖+推荐省赛"


def test_a_name_inside_a_table_row_is_evidence():
    assert text_names_entity("李明辉的综测可以评国家励志奖学金吗", GRADE_ROW) is True


def test_a_name_that_occupies_its_own_cell_is_evidence():
    """The window ``李明`` has to match the cell ``李明辉``, not equal it."""
    assert text_names_entity("李明辉进省赛了吗", COMPETITION) is True


def test_a_prose_mention_is_not_evidence():
    """``图书馆`` appears in a prose line: that cannot say how many books may be borrowed."""
    assert text_names_entity("图书馆一次最多可以借几本书？", PROSE) is False


def test_degenerate_input_is_not_evidence():
    """Routing runs on every question: an empty question or chunk must fall through."""
    assert text_names_entity("", GRADE_ROW) is False
    assert text_names_entity("李明辉的综测是多少", "") is False


def test_a_long_description_row_does_not_borrow_the_name():
    """A job-description row is tabular too; the entity still has to be in it."""
    description = "002000 中央办公厅 老干部局 综合管理岗位一级主任科员及以下 普通职位"

    assert text_names_entity("李明辉的综测是多少", description) is False


def test_one_character_terms_are_not_entity_evidence():
    """``加5分`` yields the single-character term ``分``, which matches almost any table.

    Measured: letting it count added the civil-service spreadsheet to two answerable
    questions and cost their key facts (MODIFICATIONS §5.20).
    """
    assert text_names_entity("班级团员得票率达到多少以上可以加5分？", "加分细则 第一条") is False


def test_entity_evidence_files_are_ranked_by_how_often_they_name_it():
    hits = [
        ("points", GRADE_ROW),
        ("points", GRADE_ROW),
        ("practice", GRADE_ROW),
        ("pdf", PROSE),
    ]

    ranked = entity_evidence_files(
        "李明辉的综测是多少", hits, ["points", "practice", "pdf"], max_files=2
    )

    assert ranked == ["points", "practice"]


def test_entity_evidence_never_widens_the_users_selection():
    hits = [("points", GRADE_ROW)]

    assert entity_evidence_files("李明辉的综测是多少", hits, ["practice"]) == []


def test_entity_evidence_is_empty_without_a_name():
    assert entity_evidence_files("图书馆一次最多可以借几本书？", [("pdf", PROSE)], ["pdf"]) == []


def test_entity_evidence_is_empty_without_a_selection():
    """An empty selection must not turn into "search everything"."""
    assert entity_evidence_files("李明辉的综测是多少", [("points", GRADE_ROW)], []) == []


def test_entity_files_are_appended_without_duplicates():
    routed = ["notice", "pdf"]

    merged = add_entity_files(routed, ["pdf", "table", "practice"])

    assert merged == ["notice", "pdf", "table", "practice"]


def test_the_merged_file_list_is_capped():
    merged = add_entity_files(["a"], ["b", "c", "d"], max_files=2)

    assert merged == ["a", "b"]
