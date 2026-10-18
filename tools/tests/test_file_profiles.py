"""Tests for the file-profile viewer (``tools/file_profiles.py``).

The tool is how a person reads the profile stored in ``Source.note["summary"]`` without
opening SQLite. It is read-only, so the tests build a throwaway database instead of
touching the real one.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path

import pytest

from tools.file_profiles import (
    main,
    profile_body,
    read_files,
    render,
    source_tables,
)

SUMMARY = "文件：表.xlsx\n内容摘录：学号 姓名 学时"


@pytest.fixture
def workdir():
    path = Path(tempfile.gettempdir()) / f"profiles-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def build_db(path: Path, profile: str | None = SUMMARY) -> Path:
    connection = sqlite3.connect(path)
    connection.execute(
        "create table index__1__source (id text, name text, note text, size integer)"
    )
    connection.execute(
        "create table index__1__index "
        "(target_id text, source_id text, relation_type text)"
    )
    note = {"loader": "PandasExcelReader", "tokens": 12}
    if profile:
        note["summary"] = profile
    connection.execute(
        "insert into index__1__source values (?, ?, ?, ?)",
        ("file-1", "表.xlsx", json.dumps(note, ensure_ascii=False), 2048),
    )
    connection.execute(
        "insert into index__1__index values ('d1', 'file-1', 'document')"
    )
    connection.execute(
        "insert into index__1__index values ('v1', 'file-1', 'vector')"
    )
    connection.commit()
    connection.close()
    return path


def test_only_per_file_tables_are_picked_up():
    tables = ["index__1__source", "index__1__index", "index__2__source", "file"]

    assert source_tables(tables) == ["index__1__source", "index__2__source"]


def test_the_profile_prefix_is_stripped_for_display():
    assert profile_body(SUMMARY) == "学号 姓名 学时"
    assert profile_body(None) == ""
    assert profile_body("文件：只有名字") == "文件：只有名字"


def test_counts_and_profile_are_read_from_the_database(workdir):
    db = build_db(workdir / "sql.db")
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)

    files = read_files(connection, "index__1__source", "index__1__index")

    assert len(files) == 1
    assert files[0]["chunks"] == 1
    assert files[0]["vectors"] == 1
    assert files[0]["loader"] == "PandasExcelReader"
    assert files[0]["profile"] == SUMMARY


def test_a_file_without_a_profile_is_flagged_in_the_output(workdir):
    empty = read_files(
        sqlite3.connect(
            f"file:{build_db(workdir / 'empty.db', profile=None)}?mode=ro", uri=True
        ),
        "index__1__source",
        "index__1__index",
    )

    assert "尚未生成" in render(empty)


def test_the_tool_prints_the_table_and_writes_json(workdir, capsys):
    db = build_db(workdir / "sql.db")
    json_out = workdir / "out.json"

    code = main(["--db", str(db), "--json", str(json_out)])

    printed = capsys.readouterr().out
    assert code == 0
    assert "表.xlsx" in printed and "block" not in printed
    assert "档案：" in printed
    assert json.loads(json_out.read_text(encoding="utf-8"))[0]["name"] == "表.xlsx"


def test_a_missing_database_exits_non_zero(workdir, capsys):
    assert main(["--db", str(workdir / "nope.db")]) == 2
    assert "no database" in capsys.readouterr().out
