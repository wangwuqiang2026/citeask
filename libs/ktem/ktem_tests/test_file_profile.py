"""Tests for how a file's profile is shown (``ktem.utils.file_profile``).

Indexing stores "what this file is about" in ``Source.note["summary"]`` and file routing
compares a question against it. A person needs to see the same text — that is what the
``profile`` column of the file list renders, and what ``tools/file_profiles.py`` prints
(MODIFICATIONS §5.14/§5.17).
"""

from __future__ import annotations

from ktem.utils.file_profile import profile_text, describe_profile

SUMMARY = (
    "文件：某班级社会实践完成情况表.xlsx\n"
    "内容摘录：班级简称 学号 姓名 社会实践已修学时 社会实践待修学时 最近一次社会实践完成年份"
)


def test_the_file_name_prefix_is_not_repeated():
    assert profile_text(SUMMARY).startswith("班级简称")


def test_the_excerpt_is_collapsed_to_one_line():
    one_line = profile_text(SUMMARY)

    assert "\n" not in one_line
    assert "  " not in one_line


def test_the_list_shows_a_truncated_excerpt():
    text = describe_profile({"summary": SUMMARY}, limit=10)

    assert text.endswith("...")
    assert len(text) <= 13


def test_a_file_without_a_profile_shows_a_dash():
    assert describe_profile({}) == "-"
    assert describe_profile({"summary": ""}) == "-"
    assert describe_profile(None) == "-"
    assert describe_profile("not a dict") == "-"


def test_a_profile_is_printed_in_full_when_it_fits():
    text = describe_profile({"summary": SUMMARY}, limit=500)

    assert "社会实践待修学时" in text
    assert not text.endswith("...")


def test_the_list_can_show_the_excerpt_without_an_ellipsis():
    """The file table shows the text itself; "..." is opt-in (the full profile lives in
    the detail panel under the table)."""
    with_dots = describe_profile({"summary": SUMMARY}, limit=10)
    without_dots = describe_profile({"summary": SUMMARY}, limit=10, suffix="")

    assert with_dots.endswith("...")
    assert not without_dots.endswith("...")
    assert len(without_dots) == 10
