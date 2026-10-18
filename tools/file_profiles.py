#!/usr/bin/env python
"""Show what the app understands each indexed file to be.

Indexing stores a short profile per file in ``Source.note["summary"]`` — file name plus
three excerpts (first / middle / last chunk). File routing compares a question against
those profiles, and this tool is where a human can read them: it is the answer to "what
did the app think this file is about?" without opening the SQLite file.

    python tools/file_profiles.py                 # every file
    python tools/file_profiles.py --name 综测      # filter by name
    python tools/file_profiles.py --json out.json # machine readable
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "ktem_app_data" / "user_data" / "sql.db"

#: The stored profile starts with ``文件：<name>``; the tool already prints the name.
PROFILE_BODY_MARKER = "内容摘录："


def profile_body(summary: Optional[str]) -> str:
    """The profile without its redundant file-name prefix, single spaced."""
    text = " ".join(str(summary or "").split())
    if PROFILE_BODY_MARKER in text:
        text = text.split(PROFILE_BODY_MARKER, 1)[1]
    return text.strip()


def list_tables(connection: sqlite3.Connection) -> list[str]:
    """Per-index tables are named ``index__<id>__source`` / ``index__<id>__index``."""
    rows = connection.execute(
        "select name from sqlite_master where type='table'"
    ).fetchall()
    return [row[0] for row in rows]


def source_tables(tables: list[str]) -> list[str]:
    """Per-file tables: ``index__<id>__source``."""
    return [
        name
        for name in tables
        if name.startswith("index__") and name.endswith("__source")
    ]


def read_files(
    connection: sqlite3.Connection, source_table: str, index_table: str
) -> list[dict[str, Any]]:
    """One record per indexed file: name, chunk/vector counts and its profile."""
    rows = connection.execute(
        f"select id, name, note, size from {source_table}"
    ).fetchall()
    files = []
    for file_id, name, note, size in rows:
        try:
            parsed = json.loads(note) if note else {}
        except (TypeError, ValueError):
            parsed = {}

        docs = connection.execute(
            f"select count(*) from {index_table} "
            "where source_id=? and relation_type='document'",
            (file_id,),
        ).fetchone()[0]
        vectors = connection.execute(
            f"select count(*) from {index_table} "
            "where source_id=? and relation_type='vector'",
            (file_id,),
        ).fetchone()[0]

        files.append(
            {
                "id": file_id,
                "name": name,
                "size": size,
                "chunks": docs,
                "vectors": vectors,
                "loader": parsed.get("loader"),
                "tokens": parsed.get("tokens"),
                "profile": parsed.get("summary") or "",
                "error": parsed.get("error"),
            }
        )
    files.sort(key=lambda item: str(item["name"]))
    return files


def render(files: list[dict[str, Any]]) -> str:
    lines = []
    for item in files:
        lines.append(f"■ {item['name']}")
        counters = " / ".join(
            f"{label} {item.get(key) or '-'}"
            for key, label in (
                ("chunks", "块数"),
                ("vectors", "向量"),
                ("loader", "loader"),
                ("tokens", "tokens"),
            )
        )
        lines.append(f"  {counters}")
        if item.get("error"):
            lines.append(f"  错误：{item['error']}")
        profile = profile_body(item.get("profile"))
        lines.append(
            f"  档案：{profile}" if profile else "  档案：（尚未生成，首次检索会自动补齐）"
        )
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB), help="path to sql.db")
    parser.add_argument(
        "--name", default=None, help="only files whose name contains this"
    )
    parser.add_argument(
        "--json", dest="json_out", default=None, help="write JSON here"
    )
    parser.add_argument(
        "--full", action="store_true", help="do not truncate the profile"
    )
    args = parser.parse_args(argv)

    if not Path(args.db).exists():
        print(f"no database at {args.db}")
        return 2

    connection = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    tables = list_tables(connection)
    sources = source_tables(tables)
    if not sources:
        print(f"no indexed files in {args.db}")
        return 2

    files: list[dict[str, Any]] = []
    for table in sources:
        index_table = table[: -len("__source")] + "__index"
        files.extend(read_files(connection, table, index_table))
    connection.close()

    if args.name:
        needle = args.name.lower()
        files = [item for item in files if needle in str(item["name"]).lower()]
    if not files:
        print("no matching files")
        return 2

    if not args.full:
        for item in files:
            profile = profile_body(item.get("profile"))
            item["profile"] = profile[:300] + ("..." if len(profile) > 300 else "")

    print(render(files))
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(files, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\njson -> {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
