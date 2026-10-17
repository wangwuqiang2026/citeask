#!/usr/bin/env python
"""Retrieval-only evaluation harness.

Measures the retrieval stage on its own, so it costs no LLM tokens: no model is
called here, only the documents that would reach the model are inspected.

Per question, the expected page(s) are looked up in the ranked result list:

* ``Hit@k`` — is a chunk from an expected page within the first k results?
* ``MRR``   — 1 / rank of the first such chunk over the whole result list.
* ``facts`` — are the expected key facts present in the top-k text? This is what
  the answer model actually sees, so it catches "right page, wrong chunk" cases
  that a page-level check alone would miss.

Run it with the application stopped (they share the sqlite / LanceDB files):

    python tools/eval_retrieval.py --eval tools/eval/zh-points-rules.json

The result list is limited by the retriever's own ``num_retrieval`` setting, so
Hit@k above that number is meaningless; the report prints the corpus size next to
the metrics for the same reason.

The evaluation set carries the corpus file name, which is what ties a question to
the file it must be answered from. The committed set uses a desensitized name, so
on a corpus of your own pass ``--corpus "your file name"`` to override it.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# matching helpers
# --------------------------------------------------------------------------- #
def normalize(text: Any) -> str:
    """Drop every whitespace character, so OCR line breaks do not break matching."""
    return "".join(str(text or "").split())


def normalize_name(name: Any) -> str:
    """Compare file names ignoring whitespace and punctuation.

    The uploaded name and the stored one may differ by punctuation: Gradio
    sanitizes `…（2025修订）.pdf` into `…2025修订.pdf`, so an exact comparison
    against the eval set would never match.
    """
    return "".join(ch for ch in str(name or "") if ch.isalnum())


def load_eval_set(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "questions" not in data:
        raise SystemExit(f"{path}: missing 'questions'")
    return data


# --------------------------------------------------------------------------- #
# the application
# --------------------------------------------------------------------------- #
def pick_index(app: Any, index_id: int | None) -> Any:
    """Return the file index to evaluate against."""
    indices = list(getattr(app.index_manager, "indices", []))
    if not indices:
        raise SystemExit("no index is configured")
    if index_id is not None:
        for index in indices:
            if getattr(index, "id", None) == index_id:
                return index
        raise SystemExit(f"index {index_id} not found")
    for index in indices:
        if type(index).__name__ == "FileIndex":
            return index
    return indices[0]


def resolve_user_id(index: Any, corpus: str, explicit: str | None) -> str | None:
    """Find the owner of the corpus file, unless one is given."""
    if explicit:
        return explicit
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from ktem.db.models import engine

    Source = index._resources["Source"]
    with Session(engine) as session:
        rows = session.execute(select(Source.name, Source.user)).all()
    for name, user in rows:
        if normalize_name(name) == normalize_name(corpus):
            return user
    if rows:
        return rows[0][1]
    return None


def all_doc_ids(index: Any, user_id: str | None) -> list[str]:
    """Every file id in scope for ``user_id`` (the "search all" selection)."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from ktem.db.models import engine

    Source = index._resources["Source"]
    statement = select(Source.id)
    if index.config.get("private", False):
        statement = statement.where(Source.user == user_id)
    with Session(engine) as session:
        return [row[0] for row in session.execute(statement).all()]


def build_retrievers(
    index: Any, settings: dict, user_id: str | None, doc_ids: list[str]
) -> list[Any]:
    """Build the retriever pipelines without touching the Gradio UI.

    ``FileIndex.get_retriever_pipelines`` resolves the selected files through the
    selector widget, which only exists once the UI is built. This mirrors that
    method while passing the selection in directly.
    """
    prefix = f"index.options.{index.id}."
    stripped = {k[len(prefix) :]: v for k, v in settings.items() if k.startswith(prefix)}

    retrievers = []
    for cls in index._retriever_pipeline_cls:
        obj = cls.get_pipeline(stripped, index.config, doc_ids)
        if obj is None:
            continue
        obj.Source = index._resources["Source"]
        obj.Index = index._resources["Index"]
        obj.VS = index._vs
        obj.DS = index._docstore
        obj.FSPath = index._fs_path
        obj.user_id = user_id
        retrievers.append(obj)
    return retrievers


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
def retrieve(retrievers: Iterable[Any], question: str, doc_ids: list[str]) -> list[Any]:
    """Run every retriever and merge, keeping the best score per document."""
    merged: dict[str, Any] = {}
    for retriever in retrievers:
        try:
            documents = retriever.run(question, doc_ids=doc_ids) or []
        except Exception as exc:  # a graph retriever may not be built
            print(f"    [warn] {type(retriever).__name__}: {exc}", file=sys.stderr)
            continue
        for doc in documents:
            key = getattr(doc, "doc_id", None) or id(doc)
            if key not in merged:
                merged[key] = doc
    return sorted(
        merged.values(), key=lambda d: getattr(d, "score", 0.0) or 0.0, reverse=True
    )


def evaluate(
    questions: list[dict], retrievers: list[Any], doc_ids: list[str], corpus: str, k: int
) -> list[dict]:
    wanted = normalize_name(corpus)
    results = []
    for question in questions:
        docs = retrieve(retrievers, question["question"], doc_ids)
        pages = {str(p) for p in question.get("expect_pages", [])}

        rank = None
        for position, doc in enumerate(docs):
            metadata = getattr(doc, "metadata", {}) or {}
            if wanted and normalize_name(metadata.get("file_name")) != wanted:
                continue
            if not pages or str(metadata.get("page_label")) in pages:
                rank = position
                break

        top = docs[:k]
        retrieved_text = normalize(" ".join(getattr(d, "text", "") or "" for d in top))
        missing = [
            raw
            for raw in question.get("expect_terms", [])
            if normalize(raw) not in retrieved_text
        ]

        results.append(
            {
                "id": question.get("id", question["question"][:20]),
                "question": question["question"],
                "expect_pages": sorted(pages),
                "rank": rank,
                "mrr": 0.0 if rank is None else 1.0 / (rank + 1),
                "terms_ok": not missing,
                "missing_terms": missing,
                "retrieved": [
                    {
                        "page": (getattr(d, "metadata", {}) or {}).get("page_label"),
                        "score": round(float(getattr(d, "score", 0.0) or 0.0), 3),
                    }
                    for d in docs
                ],
            }
        )
    return results


def summarize(results: list[dict], k: int, corpus_chunks: int) -> dict:
    def hit(at: int) -> float:
        if not results:
            return 0.0
        return sum(1 for r in results if r["rank"] is not None and r["rank"] < at) / len(
            results
        )

    return {
        "questions": len(results),
        "corpus_chunks": corpus_chunks,
        "hit_at_1": hit(1),
        "hit_at_3": hit(3),
        "hit_at_5": hit(5),
        "mrr": statistics.fmean([r["mrr"] for r in results]) if results else 0.0,
        "facts": sum(1 for r in results if r["terms_ok"]) / len(results)
        if results
        else 0.0,
        "k": k,
    }


def console_report(name: str, summary: dict, results: list[dict]) -> None:
    print()
    print(f"== {name} ==")
    print(f"{'#':<5}{'页':<6}{'名次':<6}{'事实':<6}问题")
    for r in results:
        print(
            "{id:<5}{pages:<6}{rank:<6}{terms:<6}{q}".format(
                id=r["id"],
                pages="/".join(r["expect_pages"]) or "-",
                rank="-" if r["rank"] is None else r["rank"] + 1,
                terms="OK" if r["terms_ok"] else "MISS",
                q=r["question"][:42],
            )
        )
    print()
    print(
        "Hit@1 = %.1f%%   Hit@3 = %.1f%%   Hit@5 = %.1f%%   MRR = %.3f   事实覆盖 = %.1f%%"
        % (
            summary["hit_at_1"] * 100,
            summary["hit_at_3"] * 100,
            summary["hit_at_5"] * 100,
            summary["mrr"],
            summary["facts"] * 100,
        )
    )
    print(f"语料块数 = {summary['corpus_chunks']}（Hit@k 的上限受此限制）")


def markdown_report(name: str, summary: dict, results: list[dict]) -> str:
    lines = [
        f"### 检索评测 · {name}",
        "",
        "| 指标 | 值 |",
        "|---|---|",
        f"| 问题数 | {summary['questions']} |",
        f"| 语料块数 | {summary['corpus_chunks']} |",
        f"| Hit@1 | **{summary['hit_at_1']:.1%}** |",
        f"| Hit@3 | **{summary['hit_at_3']:.1%}** |",
        f"| Hit@5 | **{summary['hit_at_5']:.1%}** |",
        f"| MRR | **{summary['mrr']:.3f}** |",
        f"| 关键事实覆盖率 | **{summary['facts']:.1%}** |",
        "",
        "<details><summary>逐题明细</summary>",
        "",
        "| # | 问题 | 期望页 | 命中名次 | 关键事实 |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            "| {id} | {q} | {pages} | {rank} | {terms} |".format(
                id=r["id"],
                q=r["question"].replace("|", "\\|"),
                pages="/".join(r["expect_pages"]) or "-",
                rank="未命中" if r["rank"] is None else r["rank"] + 1,
                terms="✅" if r["terms_ok"] else "❌ " + "、".join(r["missing_terms"]),
            )
        )
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval", required=True, help="path to the evaluation set")
    parser.add_argument("--top-k", type=int, default=5, help="window for fact checking (default: 5)")
    parser.add_argument("--index-id", type=int, default=None, help="file index to use")
    parser.add_argument("--user-id", default=None, help="owner of the corpus (default: detected)")
    parser.add_argument(
        "--corpus",
        default=None,
        help="corpus file name to score against (default: the one in the eval set)",
    )
    parser.add_argument("--out", default=None, help="write a Markdown report here")
    parser.add_argument("--json", dest="json_out", default=None, help="write raw results here")
    args = parser.parse_args(argv)

    eval_set = load_eval_set(Path(args.eval))
    corpus = args.corpus or eval_set.get("corpus", "")
    print(f"evaluation set: {eval_set.get('name', args.eval)}")
    print(f"corpus        : {corpus or '(any indexed file)'}")

    # imported here so --help works without pulling the whole application in
    sys.path.insert(0, str(REPO_ROOT))
    for lib in ("libs/ktem", "libs/kotaemon"):
        sys.path.insert(0, str(REPO_ROOT / lib))
    from ktem.main import App

    app = App()
    index = pick_index(app, args.index_id)
    settings = app.default_settings.flatten()
    user_id = resolve_user_id(index, corpus, args.user_id)
    doc_ids = all_doc_ids(index, user_id)
    print(f"index         : {type(index).__name__} (id={index.id})")
    print(f"user          : {user_id}")
    print(f"files in scope: {len(doc_ids)}")
    if not doc_ids:
        print("no file is indexed for this user — upload the corpus first")
        return 2

    retrievers = build_retrievers(index, settings, user_id, doc_ids)
    print(f"retrievers    : {', '.join(type(r).__name__ for r in retrievers)}")

    # how many chunks the corpus actually contributes, i.e. the ceiling of Hit@k
    corpus_chunks = 0
    probe = retrieve(retrievers, corpus, doc_ids) if corpus else []
    corpus_chunks = sum(
        1
        for d in probe
        if normalize_name((getattr(d, "metadata", {}) or {}).get("file_name"))
        == normalize_name(corpus)
    )

    results = evaluate(eval_set["questions"], retrievers, doc_ids, corpus, args.top_k)
    summary = summarize(results, args.top_k, corpus_chunks)
    console_report(eval_set.get("name", args.eval), summary, results)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            markdown_report(eval_set.get("name", args.eval), summary, results),
            encoding="utf-8",
        )
        print(f"markdown report -> {args.out}")
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(
                {"summary": summary, "results": results}, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
        print(f"raw results     -> {args.json_out}")
    return 0 if summary["hit_at_1"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
