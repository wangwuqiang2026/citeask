"""Tests for the refusal gate (``kotaemon.abstain`` + the chat pipeline wiring).

A question the corpus cannot answer used to be answered anyway — from the model's own
memory or from an unrelated chunk. The gate refuses when the best *similarity* is
below the calibrated threshold, and the same decision is scored by
``tools/eval_retrieval.py`` (see ``tools/eval/zh-no-answer.json``).
"""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from ktem.reasoning import simple as simple_module
from ktem.reasoning.simple import abstain_events
from kotaemon.abstain import (
    best_similarity,
    entity_terms,
    line_is_a_cell,
    named_file_evidence,
    row_looks_tabular,
    should_refuse,
    specific_term_evidence,
)


def doc(score, text="chunk"):
    return SimpleNamespace(score=score, text=text)


@pytest.fixture
def workdir():
    """Scratch directory (Path.mkdir, not tempfile.mkdtemp: the latter makes a 0o700
    directory, which is not writable inside the Windows sandbox used for local runs)."""
    path = Path(tempfile.gettempdir()) / f"abstain-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# --------------------------------------------------------------------------- #
# the decision itself
# --------------------------------------------------------------------------- #
def test_nothing_retrieved_is_always_refused():
    assert should_refuse([], 0.45) is True
    # even with the gate disabled, "nothing came back" means no answer
    assert should_refuse([], 0.0) is True


def test_a_strong_match_is_answered():
    assert should_refuse([0.71, 0.52], 0.45) is False


def test_a_weak_match_is_refused():
    assert should_refuse([0.31, 0.22], 0.45) is True


def test_keyword_only_matches_are_not_refused():
    """The hybrid retriever scores full-text matches with -1 (no similarity).

    That sentinel means "found by keyword", not "a weak match": there is no
    similarity to judge, so refusing would throw away keyword hits.
    """
    assert best_similarity([-1.0, -1.0]) is None
    assert should_refuse([-1.0, -1.0], 0.45) is False


def test_a_positive_score_wins_over_the_sentinel():
    assert best_similarity([-1.0, 0.62]) == 0.62
    assert should_refuse([-1.0, 0.62], 0.45) is False


def test_zero_threshold_disables_the_similarity_check():
    assert should_refuse([0.1], 0.0) is False


def test_broken_scores_do_not_crash_the_gate():
    assert best_similarity([None, "bad", 0.5]) == 0.5


# --------------------------------------------------------------------------- #
# the documents the gate emits
# --------------------------------------------------------------------------- #
def test_weak_evidence_produces_an_info_panel_and_a_refusal(monkeypatch):
    logged = []
    monkeypatch.setattr(
        simple_module, "log_abstention", lambda q, s, t: logged.append((q, s, t))
    )

    events = abstain_events("食堂几点开门？", [doc(0.30)], threshold=0.45)

    assert [e.channel for e in events] == ["info", "chat"]
    assert "0.30" in events[0].content
    assert "0.45" in events[1].content
    assert logged == [("食堂几点开门？", 0.30, 0.45)]


def test_strong_evidence_emits_nothing(monkeypatch):
    monkeypatch.setattr(simple_module, "log_abstention", lambda *a: None)

    assert abstain_events("问", [doc(0.80)], threshold=0.45) == []


def test_the_refusal_is_written_to_the_audit_log(monkeypatch, workdir):
    log_file = workdir / "abstained.jsonl"
    monkeypatch.setattr(simple_module, "abstain_log_path", lambda: log_file)

    abstain_events("宿舍几点熄灯？", [doc(0.32)], threshold=0.45)

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["question"] == "宿舍几点熄灯？"
    assert record["best_score"] == 0.32
    assert record["threshold"] == 0.45
    assert record["time"]


def test_a_log_failure_does_not_break_the_answer_path(monkeypatch, workdir):
    """The gate must still refuse if the log is not writable."""
    blocked = workdir / "no" / "such"
    blocked.parent.mkdir()
    blocked.write_text("blocked", encoding="utf-8")
    monkeypatch.setattr(
        simple_module, "abstain_log_path", lambda: blocked / "x.jsonl"
    )

    events = abstain_events("q", [doc(0.1)], threshold=0.45)

    assert len(events) == 2


@pytest.mark.parametrize("scores,expected", [([0.44], True), ([0.45], False)])
def test_the_threshold_is_inclusive(scores, expected):
    assert should_refuse(scores, 0.45) is expected


# --------------------------------------------------------------------------- #
# table rows: a name in a spreadsheet row is evidence at a low similarity
# --------------------------------------------------------------------------- #
TABLE_ROW = (
    "某班级,24405010001,李明辉,8,24,2025上半年8学时,"
    "某班级,24405010002,孙梅,4,24,2025上半年16学时"
)
PROSE = (
    "第七条 在图书馆借阅思想政治类书籍，每学期每次加 2 分，最高不超过 10 分。"
)


def row_doc(score, text=TABLE_ROW):
    return SimpleNamespace(score=score, text=text)


def test_entity_terms_are_three_character_windows():
    terms = entity_terms("李明辉的社会实践完成了吗")

    assert "李明辉" in terms  # the name the table actually contains
    assert "社会实践" not in terms  # windows are 3 characters long
    assert "2025" in entity_terms("2025 年的学时")  # digits survive intact


def test_a_table_row_naming_the_row_counts_as_evidence():
    """The case that made the gate wrong: 0.38 for the row that *does* name the student.

    A global threshold calibrated on prose refuses it, although the corpus contains the
    answer — a dense row simply embeds far from a natural-language question.
    """
    documents = [row_doc(0.38)]

    assert should_refuse([0.38], 0.45) is True  # the old, misleading answer
    assert (
        should_refuse(
            [0.38],
            0.45,
            documents=documents,
            question="李明辉的社会实践完成了吗",
            term_floor=0.33,
        )
        is False
    )


def test_below_the_term_floor_it_is_still_refused():
    """0.30 for "李明辉的体重是多少": the row exists, the attribute does not."""
    documents = [row_doc(0.30)]

    assert (
        should_refuse(
            [0.30],
            0.45,
            documents=documents,
            question="李明辉的身高是多少",
            term_floor=0.33,
        )
        is True
    )


def test_a_prose_mention_is_not_evidence():
    """``图书馆`` appears in the points-rules document, but that sentence cannot say how
    many books may be borrowed — answering would invent an answer."""
    documents = [row_doc(0.40, text=PROSE)]

    assert specific_term_evidence("图书馆一次最多可以借几本书？", documents) is False
    assert (
        should_refuse(
            [0.40],
            0.45,
            documents=documents,
            question="图书馆一次最多可以借几本书？",
            term_floor=0.33,
        )
        is True
    )


def test_row_looks_tabular_needs_numbered_fields():
    assert row_looks_tabular(TABLE_ROW) is True
    assert row_looks_tabular(PROSE) is False
    assert row_looks_tabular("李明辉") is False


def test_without_documents_the_decision_is_unchanged():
    assert should_refuse([0.38], 0.45) is True
    assert should_refuse([0.38], 0.45, documents=None, question="李明辉") is True


def test_a_topic_word_in_every_chunk_is_not_evidence():
    """``加分细则`` appears in most chunks: that is the topic, not a specific row."""
    documents = [row_doc(0.40, text="加分细则 第一条 加分细则如下")] * 5

    assert specific_term_evidence("加分细则怎么算", documents) is False


def test_evidence_without_a_term_or_a_text_is_not_evidence():
    """Degenerate input must fall through, not raise (the gate runs on every answer)."""
    assert specific_term_evidence("", [row_doc(0.40)]) is False
    assert specific_term_evidence("李明辉的社会实践完成了吗", []) is False


def test_require_tabular_false_accepts_any_verbatim_match():
    """The escape hatch used by tests/tools: every verbatim hit counts, twice over."""
    documents = [row_doc(0.40, text="李明辉 75.45"), row_doc(0.40, text="李明辉 75.45")]

    assert specific_term_evidence("李明辉", documents) is False  # not a row, not a cell
    assert specific_term_evidence("李明辉", documents, require_tabular=False) is True


def test_abstain_events_answers_a_table_row_below_the_threshold(monkeypatch):
    """End to end through the pipeline helper: no refusal event is emitted."""
    monkeypatch.setattr(simple_module, "abstain_threshold", lambda: 0.45)
    monkeypatch.setattr(simple_module, "abstain_term_floor", lambda: 0.33)
    monkeypatch.setattr(simple_module, "log_abstention", lambda *a: None)

    events = abstain_events(
        "李明辉的社会实践完成了吗", [row_doc(0.38)], threshold=0.45
    )

    assert events == []


# --------------------------------------------------------------------------- #
# vertical tables: a PDF/OCR loader writes one cell per line, not one row per line
# --------------------------------------------------------------------------- #
VERTICAL_ROW = (
    "2026年学科竞赛校赛成绩\n序号\n队名\n成员1（队长）\n成员2\n成员3\n奖项\n"
    "9\n远航队\n林静怡\n高文静\n程雅琴\n二等奖+推荐省赛\n"
    "10\n星河队\n赵一鸣\n钱二毛\n李明辉\n二等奖+推荐省赛\n"
    "11\n青柏队\n马俊杰\n方志成\n罗晓博\n二等奖+推荐省赛\n"
)


def test_a_name_on_its_own_line_is_a_cell():
    assert row_looks_tabular("李明辉") is False  # one field is not a row
    assert line_is_a_cell("李明辉", "李明辉") is True
    assert line_is_a_cell("  李明辉 ", "李明辉") is True  # loader padding
    assert line_is_a_cell("| 李明辉 |", "李明辉") is True
    assert line_is_a_cell("钱二毛", "李明辉") is False
    assert line_is_a_cell(PROSE, "图书馆") is False  # a prose line is a sentence


def test_a_vertical_table_row_counts_as_evidence():
    """The case behind MODIFICATIONS §5.19: 0.412 for the chunk that *does* name the student.

    The row is rendered one cell per line, so the row test cannot see it; without the
    cell test the gate refuses a question whose answer is in the context.
    """
    documents = [row_doc(0.412, text=VERTICAL_ROW)]

    assert specific_term_evidence("李明辉进省赛了吗", documents) is True
    assert (
        should_refuse(
            [0.412],
            0.45,
            documents=documents,
            question="李明辉进省赛了吗",
            term_floor=0.33,
        )
        is False
    )


def test_a_prose_mention_is_still_not_evidence_next_to_a_vertical_table():
    documents = [row_doc(0.412, text=PROSE)]

    assert specific_term_evidence("图书馆一次最多可以借几本书？", documents) is False
    assert (
        should_refuse(
            [0.412],
            0.45,
            documents=documents,
            question="图书馆一次最多可以借几本书？",
            term_floor=0.33,
        )
        is True
    )


def test_a_vertical_cell_below_the_term_floor_is_still_refused():
    """0.30 is too weak to answer even with the name on its own line."""
    documents = [row_doc(0.30, text=VERTICAL_ROW)]

    assert (
        should_refuse(
            [0.30],
            0.45,
            documents=documents,
            question="李明辉进省赛了吗",
            term_floor=0.33,
        )
        is True
    )


def test_a_name_absent_from_the_vertical_table_is_not_evidence():
    documents = [row_doc(0.40, text=VERTICAL_ROW)]

    assert specific_term_evidence("陈志强进省赛了吗", documents) is False


def test_abstain_events_answers_a_vertical_table_below_the_threshold(monkeypatch):
    monkeypatch.setattr(simple_module, "abstain_threshold", lambda: 0.45)
    monkeypatch.setattr(simple_module, "abstain_term_floor", lambda: 0.33)
    monkeypatch.setattr(simple_module, "log_abstention", lambda *a: None)

    events = abstain_events(
        "李明辉进省赛了吗", [row_doc(0.412, text=VERTICAL_ROW)], threshold=0.45
    )

    assert events == []


# --------------------------------------------------------------------------- #
# a question that names the file (§5.22): source code answers at 0.34-0.39
# --------------------------------------------------------------------------- #
def file_doc(score, name, text="def gaussian(X, num_centers=10, sigma=1.0): ..."):
    return SimpleNamespace(score=score, text=text, metadata={"file_name": name})


def test_a_question_that_names_the_file_is_answered_below_the_threshold():
    """Measured: the code file against a Chinese question scores 0.34-0.39 (§5.22)."""
    documents = [file_doc(0.35, "代码.txt"), file_doc(0.30, "通知.docx")]

    assert named_file_evidence("代码文件夹描述了什么算法", documents) is True
    assert (
        should_refuse(
            [0.35, 0.30],
            0.45,
            documents=documents,
            question="代码文件夹描述了什么算法",
            term_floor=0.33,
        )
        is False
    )


def test_the_file_name_test_does_not_fire_by_accident():
    documents = [file_doc(0.35, "计算机学院关于校级奖学金评定官网通知.docx")]

    assert named_file_evidence("奖学金怎么评", documents) is False
    assert (
        should_refuse(
            [0.35],
            0.45,
            documents=documents,
            question="奖学金怎么评",
            term_floor=0.33,
        )
        is True
    )


def test_a_file_that_was_not_retrieved_cannot_vouch_for_anything():
    documents = [file_doc(0.35, "通知.docx")]

    assert named_file_evidence("代码里用了什么算法", documents) is False


def test_a_stem_too_short_to_identify_is_ignored():
    assert named_file_evidence("a 是什么", [file_doc(0.35, "a.txt")]) is False
    assert named_file_evidence("", [file_doc(0.35, "代码.txt")]) is False


def test_naming_the_file_does_not_answer_a_very_weak_match():
    """0.30 is too weak even when the question names the file."""
    documents = [file_doc(0.30, "代码.txt")]

    assert (
        should_refuse(
            [0.30],
            0.45,
            documents=documents,
            question="代码里用了什么算法",
            term_floor=0.33,
        )
        is True
    )


def test_abstain_events_answers_a_named_file_below_the_threshold(monkeypatch):
    monkeypatch.setattr(simple_module, "abstain_threshold", lambda: 0.45)
    monkeypatch.setattr(simple_module, "abstain_term_floor", lambda: 0.33)
    monkeypatch.setattr(simple_module, "log_abstention", lambda *a: None)

    events = abstain_events(
        "这个代码用了什么算法", [file_doc(0.39, "代码.txt")], threshold=0.45
    )

    assert events == []
