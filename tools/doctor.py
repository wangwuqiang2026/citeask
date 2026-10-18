#!/usr/bin/env python
"""Self-check for the running configuration and the indexed corpus.

This project has shipped three defects of the same shape — a switch or a reader was
"configured", the code path was short-circuited or the exception was swallowed, and
nothing on screen said so (a retrieval scope that resolved to nothing, a scanned PDF
whose text layer held only headings, a `.docx`/`.xls` whose reader raised, see
MODIFICATIONS.md §2.7–§2.10). A paragraph in the docs does not stop that from
happening again; a command that fails loudly does.

    python tools/doctor.py              # human-readable table
    python tools/doctor.py --json       # machine-readable findings
    python tools/doctor.py --strict     # warnings fail the check as well

Exit codes: 0 healthy, 1 problems found, 2 could not run (no index / no files).

Run it with the application stopped (they share the sqlite / LanceDB files).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

OK = "OK"
WARN = "WARN"
FAIL = "FAIL"
_STATUS_ORDER = {OK: 0, WARN: 1, FAIL: 2}

#: how many chunks to inspect for empty text per source (the docstore get is cheap,
#: but a spreadsheet can contribute ten thousand chunks)
CHUNK_SAMPLE = 200


# --------------------------------------------------------------------------- #
# findings (pure: the tests drive these directly)
# --------------------------------------------------------------------------- #
def finding(check: str, status: str, detail: str = "") -> dict[str, str]:
    return {"check": check, "status": status, "detail": detail}


def file_finding(row: dict[str, Any]) -> dict[str, str]:
    """One finding per indexed file: is it actually retrievable?

    A file with a source row but no vector chunks is the shape a failed indexing run
    leaves behind: it is listed, looks indexed, and answers nothing. Documents
    without vectors count as broken for the same reason — retrieval reads vectors.
    """
    name = str(row.get("name", "?"))
    vectors = int(row.get("vectors") or 0)
    documents = int(row.get("documents") or 0)
    note = row.get("note") or {}

    if vectors == 0:
        reason = note.get("error") or "indexing never finished"
        return finding(
            f"文件 {name}",
            FAIL,
            f"0 个向量块（{documents} 个文档块），检索永远命中不到；原因：{reason}",
        )
    if note.get("error"):
        return finding(f"文件 {name}", WARN, f"上次索引报错：{note['error']}")
    if not note.get("loader"):
        return finding(f"文件 {name}", WARN, "没有记录读取器/词数，索引可能未完成")
    return finding(
        f"文件 {name}",
        OK,
        f"{documents} 块 / {vectors} 向量 / loader={note.get('loader')} "
        f"/ {note.get('tokens', '-')} tokens",
    )


def empty_chunk_finding(checked: int, empty: int) -> dict[str, str]:
    """Chunks whose text is empty cannot answer anything — they only take slots."""
    if checked == 0:
        return finding("空文本块", WARN, "没有可检查的块")
    ratio = empty / checked
    detail = f"抽检 {checked} 块，{empty} 块正文为空（{ratio:.0%}）"
    if ratio > 0.2:
        return finding("空文本块", FAIL, detail + "，检索名额被空块占用")
    if empty:
        return finding("空文本块", WARN, detail)
    return finding("空文本块", OK, detail)


def reranker_finding(name: str, has_key: bool, enabled: bool) -> dict[str, str]:
    """Without credentials a reranker now falls back instead of doing nothing."""
    if not enabled:
        return finding("配置：重排", OK, "未启用重排（检索按向量分排序）")
    if not has_key:
        return finding(
            "配置：重排",
            WARN,
            f"{name} 没有 API key：会回退到本地词法重排（可用、但不如语义重排；"
            "见 ROADMAP B2 / MODIFICATIONS §5.9）",
        )
    return finding("配置：重排", OK, f"{name} 已配置 key")


def effective_chunk_size(index_value: Any, default_value: Any) -> int:
    """The chunk size indexing will actually use.

    ``index.config["chunk_size"]`` is 0 unless someone overrode it per index; the
    fallback lives in ``flowsettings.FILE_INDEX_PIPELINE_SPLITTER_CHUNK_SIZE``.
    Reading only the index value reported "按页成块" while the pipeline was splitting
    by token — a stale warning is as bad as a missing one.
    """
    value = int(index_value or 0) or int(default_value or 0)
    return max(value, 0)


def chunk_size_finding(chunk_size: int) -> dict[str, str]:
    if chunk_size and chunk_size > 0:
        return finding("配置：切块", OK, f"chunk_size={chunk_size}（按 token 切块）")
    return finding(
        "配置：切块",
        WARN,
        "chunk_size=0（按页成块，块偏粗；见 ROADMAP B3）",
    )


def smoke_finding(rows: list[dict[str, Any]]) -> dict[str, str]:
    """Retrieval smoke: did each fixed question return anything at all?"""
    if not rows:
        return finding("检索 smoke", WARN, "没有执行（缺少评测题或 --skip-retrieval）")
    empty = [row for row in rows if not row.get("retrieved")]
    page_hits = [row for row in rows if row.get("page_hit")]
    found = len(rows) - len(empty)
    detail = (
        f"{found}/{len(rows)} 题有召回，"
        f"{len(page_hits)}/{len(rows)} 题命中期望页"
    )
    if empty:
        return finding("检索 smoke", FAIL, detail + "；有题目完全召回为空")
    return finding("检索 smoke", OK, detail)


def exit_code(findings: Iterable[dict[str, str]], *, strict: bool = False) -> int:
    """0 healthy, 1 problems. ``strict`` also fails on warnings."""
    worst = max((_STATUS_ORDER.get(f["status"], 0) for f in findings), default=0)
    if worst >= _STATUS_ORDER[FAIL]:
        return 1
    if strict and worst >= _STATUS_ORDER[WARN]:
        return 1
    return 0


def render_table(findings: list[dict[str, str]]) -> str:
    lines = ["| 检查项 | 状态 | 说明 |", "|---|---|---|"]
    for item in findings:
        status = {OK: "OK", WARN: "⚠ WARN", FAIL: "❌ FAIL"}.get(
            item["status"], item["status"]
        )
        lines.append(
            "| {check} | {status} | {detail} |".format(
                check=item["check"],
                status=status,
                detail=str(item["detail"]).replace("|", "\\|"),
            )
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# data collection (talks to the application)
# --------------------------------------------------------------------------- #
def collect_sources(index: Any) -> list[dict[str, Any]]:
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from ktem.db.models import engine

    Source = index._resources["Source"]
    Index = index._resources["Index"]
    with Session(engine) as session:
        rows = session.execute(select(Source.id, Source.name, Source.note)).all()
        counts = session.execute(
            select(Index.source_id, Index.relation_type, func.count()).group_by(
                Index.source_id, Index.relation_type
            )
        ).all()

    tally: dict[str, dict[str, int]] = {}
    for source_id, relation, count in counts:
        tally.setdefault(source_id, {"document": 0, "vector": 0})[relation] = count

    return [
        {
            "id": source_id,
            "name": name,
            "note": dict(note or {}),
            "documents": tally.get(source_id, {}).get("document", 0),
            "vectors": tally.get(source_id, {}).get("vector", 0),
        }
        for source_id, name, note in rows
    ]


def collect_chunk_stats(index: Any, sources: list[dict[str, Any]]) -> tuple[int, int]:
    """(checked, empty) over a sample of the document-store chunks."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from ktem.db.models import engine

    Index = index._resources["Index"]
    source_ids = [row["id"] for row in sources if row["documents"]]
    if not source_ids:
        return 0, 0

    with Session(engine) as session:
        chunk_ids = [
            row[0]
            for row in session.execute(
                select(Index.target_id)
                .where(
                    Index.relation_type == "document",
                    Index.source_id.in_(source_ids),
                )
                .limit(CHUNK_SAMPLE)
            ).all()
        ]
    if not chunk_ids:
        return 0, 0

    docs = index._docstore.get(chunk_ids) or []
    empty = sum(1 for doc in docs if not (getattr(doc, "text", "") or "").strip())
    return len(docs), empty


def collect_config(index: Any, settings: dict[str, Any]) -> dict[str, Any]:
    from ktem.embeddings.manager import embedding_models_manager
    from ktem.rerankings.manager import reranking_models_manager
    from theflow.settings import settings as flowsettings

    embedding_name = index.config.get(
        "embedding", embedding_models_manager.get_default_name()
    )
    embedding = embedding_models_manager[embedding_name]

    reranker_name = index.config.get(
        "reranking", reranking_models_manager.get_default_name()
    )
    reranker = reranking_models_manager[reranker_name]
    has_key = bool(
        getattr(reranker, "cohere_api_key", None)
        or getattr(reranker, "api_key", None)
        or getattr(reranker, "voyage_api_key", None)
    )
    use_reranking = bool(settings.get(f"index.options.{index.id}.use_reranking", False))

    catalog_entries = 0
    try:
        from ktem.utils.i18n import load_catalog

        catalog = load_catalog(getattr(flowsettings, "KH_UI_LANGUAGE", "en"))
        catalog_entries = len(getattr(catalog, "translations", {}) or {})
    except Exception:  # noqa: BLE001 - the catalog is optional for the check
        catalog_entries = 0

    return {
        "embedding_name": embedding_name,
        "embedding_model": getattr(embedding, "model_name", None)
        or getattr(embedding, "model", "?"),
        "embedding_type": type(embedding).__name__,
        "reranker_name": reranker_name,
        "reranker_has_key": has_key,
        "use_reranking": use_reranking,
        "chunk_size": effective_chunk_size(
            int(getattr(index.config, "get", lambda *_: 0)("chunk_size", 0) or 0),
            getattr(flowsettings, "FILE_INDEX_PIPELINE_SPLITTER_CHUNK_SIZE", 0),
        ),
        "pdf_ocr": bool(getattr(flowsettings, "PDF_OCR_ENABLED", True)),
        "catalog_entries": catalog_entries,
        "repair_orphans": bool(getattr(flowsettings, "KH_REPAIR_ORPHAN_FILES", True)),
    }


def collect_smoke(
    index: Any,
    settings: dict[str, Any],
    questions: list[dict[str, Any]],
    limit: int = 3,
    corpus: str = "",
) -> list[dict[str, Any]]:
    """Ask a few fixed questions and report whether anything came back.

    ``corpus`` pins the file a question must be answered from. The committed eval
    set carries a desensitized name, so when that name is not indexed the check
    falls back to "did the expected page show up at all" instead of reporting every
    question as a miss (which would make the smoke useless on a real corpus).
    """
    from tools.eval_retrieval import (
        all_doc_ids,
        build_retrievers,
        normalize_name,
        retrieve,
        resolve_user_id,
    )

    user_id = resolve_user_id(index, "", None)
    doc_ids = all_doc_ids(index, user_id)
    if not doc_ids:
        return []
    retrievers = build_retrievers(index, settings, user_id, doc_ids)

    indexed_names = {normalize_name(name) for name in indexed_file_names(index)}
    wanted_default = normalize_name(corpus)
    if wanted_default and wanted_default not in indexed_names:
        print(
            f"[doctor] 评测集的语料名 {corpus!r} 不在索引里，smoke 只检查"
            "「期望页是否出现」，不校验文件（可用 --corpus 指定）"
        )
        wanted_default = ""

    rows = []
    for question in questions:
        docs = retrieve(retrievers, question["question"], doc_ids)
        pages = {str(p) for p in question.get("expect_pages", [])}
        wanted = normalize_name(question.get("_corpus", "")) or wanted_default
        page_hit = False
        for doc in docs:
            metadata = getattr(doc, "metadata", {}) or {}
            if wanted and normalize_name(metadata.get("file_name")) != wanted:
                continue
            if not pages or str(metadata.get("page_label")) in pages:
                page_hit = True
                break
        top = docs[0] if docs else None
        rows.append(
            {
                "question": question["question"],
                "retrieved": len(docs),
                "page_hit": page_hit,
                "top": (
                    "{name} · 第 {page} 页 · {score:.3f}".format(
                        name=(getattr(top, "metadata", {}) or {}).get("file_name", "?"),
                        page=(getattr(top, "metadata", {}) or {}).get(
                            "page_label", "?"
                        ),
                        score=float(getattr(top, "score", 0.0) or 0.0),
                    )
                    if top
                    else "-"
                ),
            }
        )
    return rows


def indexed_file_names(index: Any) -> list[str]:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from ktem.db.models import engine

    Source = index._resources["Source"]
    with Session(engine) as session:
        return [row[0] for row in session.execute(select(Source.name)).all()]


def load_smoke_questions(path: Path, limit: int = 3) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    corpus = data.get("corpus", "")
    return [dict(item, _corpus=corpus) for item in data.get("questions", [])[:limit]]


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index-id", type=int, default=None, help="file index to check"
    )
    parser.add_argument(
        "--eval",
        default=str(REPO_ROOT / "tools" / "eval" / "zh-points-rules.json"),
        help="evaluation set used for the retrieval smoke questions",
    )
    parser.add_argument(
        "--corpus",
        default=None,
        help="file the smoke questions belong to (default: the eval set's corpus)",
    )
    parser.add_argument(
        "--skip-retrieval",
        action="store_true",
        help="skip the retrieval smoke (leaves the vector store untouched)",
    )
    parser.add_argument(
        "--json", dest="json_out", default=None, help="write findings here"
    )
    parser.add_argument(
        "--strict", action="store_true", help="let warnings fail the check as well"
    )
    args = parser.parse_args(argv)

    sys.path.insert(0, str(REPO_ROOT))
    for lib in ("libs/ktem", "libs/kotaemon"):
        sys.path.insert(0, str(REPO_ROOT / lib))
    from ktem.main import App

    from tools.eval_retrieval import pick_index

    app = App()
    try:
        index = pick_index(app, args.index_id)
    except SystemExit as exc:
        print(exc)
        return 2

    settings = app.default_settings.flatten()
    sources = collect_sources(index)
    findings: list[dict[str, str]] = []
    findings += [file_finding(row) for row in sources]

    checked, empty = collect_chunk_stats(index, sources)
    findings.append(empty_chunk_finding(checked, empty))

    config = collect_config(index, settings)
    findings.append(
        finding(
            "配置：向量",
            OK,
            f"{config['embedding_name']} → {config['embedding_type']}"
            f"（{config['embedding_model']}）",
        )
    )
    findings.append(
        reranker_finding(
            config["reranker_name"], config["reranker_has_key"], config["use_reranking"]
        )
    )
    findings.append(chunk_size_finding(config["chunk_size"]))
    findings.append(
        finding(
            "配置：PDF OCR",
            OK if config["pdf_ocr"] else WARN,
            "已开启" if config["pdf_ocr"] else "已关闭：扫描件只会得到标题文字",
        )
    )
    findings.append(
        finding(
            "配置：启动自愈",
            OK if config["repair_orphans"] else WARN,
            "已开启（修复有行无向量的文件）" if config["repair_orphans"] else "已关闭",
        )
    )
    findings.append(
        finding(
            "配置：中文词表",
            OK if config["catalog_entries"] else WARN,
            (
                f"{config['catalog_entries']} 条"
                if config["catalog_entries"]
                else "未加载"
            ),
        )
    )

    smoke_rows: list[dict[str, Any]] = []
    if not args.skip_retrieval and sources:
        questions = load_smoke_questions(Path(args.eval))
        smoke_corpus = args.corpus
        if smoke_corpus is None and questions:
            smoke_corpus = str(questions[0].get("_corpus", ""))
        smoke_rows = collect_smoke(
            index, settings, questions, corpus=smoke_corpus or ""
        )
    findings.append(smoke_finding(smoke_rows))

    print(render_table(findings))
    if smoke_rows:
        print()
        print("检索 smoke 明细：")
        for row in smoke_rows:
            print(
                "  {mark} {q} → 召回 {n} 条，Top1 {top}".format(
                    mark="✔" if row["page_hit"] else "✘",
                    q=row["question"][:36],
                    n=row["retrieved"],
                    top=row["top"],
                )
            )

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(
                {"findings": findings, "smoke": smoke_rows, "config": config},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nfindings -> {args.json_out}")

    total = len([f for f in findings if f["status"] == FAIL])
    warnings = len([f for f in findings if f["status"] == WARN])
    print(f"\n{len(findings)} 项检查：{total} FAIL / {warnings} WARN")
    return exit_code(findings, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
