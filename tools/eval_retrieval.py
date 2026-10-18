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

Questions may carry a ``category`` (e.g. ``T1`` single-hop, ``T2`` numeric detail,
``T3`` multi-hop, ``T4`` unanswerable — see ``tools/eval/README.md``). When they do,
the report breaks the metrics down per category: an overall Hit@1 hides the fact
that a change helps easy questions and hurts the ones that matter.

Run it with the application stopped (they share the sqlite / LanceDB files):

    python tools/eval_retrieval.py --eval tools/eval/zh-points-rules.json

Useful switches:

* ``--category T2`` — score one category only;
* ``--rerank off|on`` — pin the reranker for an A/B run (default: the app setting);
* ``--fail-under-hit1 0.55`` — exit non-zero when Hit@1 falls below the threshold,
  so the command can gate CI (without it the exit code is always 0 for a completed
  run: a 60% baseline is not a failure).

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
import time
from pathlib import Path
from typing import Any, Iterable

from kotaemon.abstain import best_similarity, should_refuse, specific_term_evidence

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


#: Questions of the committed set carry no ``category``; they all report here.
DEFAULT_CATEGORY = "未分类"


def category_of(question: dict) -> str:
    """The category a question scores into (see ``tools/eval/README.md``)."""
    return str(question.get("category") or DEFAULT_CATEGORY)


def is_abstain_case(question: dict) -> bool:
    """A question the corpus cannot answer: success means refusing to answer."""
    return question.get("expect_answer", True) is False


def top_score_of(docs: Iterable[Any]) -> float:
    """Best retrieval score of a result list (0.0 when nothing came back)."""
    return max((float(getattr(d, "score", 0.0) or 0.0) for d in docs), default=0.0)


def scores_of(docs: Iterable[Any]) -> list[float]:
    """Raw scores of a result list, as the refusal gate sees them."""
    return [float(getattr(d, "score", 0.0) or 0.0) for d in docs]


def percentile(values: Iterable[float], fraction: float) -> float:
    """Linear-interpolated percentile (0.5 = median, 0.95 = p95).

    Reported next to the metrics because every retrieval-side change — a reranker,
    a different top_k — trades quality for latency, and that trade has to be visible
    in the same table.
    """
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


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


def pick_doc_ids(rows: list[tuple[str, str]], scope: str) -> list[str]:
    """Ids of the files whose name contains ``scope`` (normalized comparison).

    This mirrors the app's "search in file(s)" mode. It matters for measurement: an
    index that also holds a 10k-chunk spreadsheet dilutes the recall of a four-chunk
    PDF, so the per-corpus numbers have to be reproducible with the same scope the
    claim was made under.
    """
    wanted = normalize_name(scope)
    if not wanted:
        return [row[0] for row in rows]
    return [row[0] for row in rows if wanted in normalize_name(row[1])]


def build_retrievers(
    index: Any,
    settings: dict,
    user_id: str | None,
    doc_ids: list[str],
    rerank: bool | None = None,
) -> list[Any]:
    """Build the retriever pipelines without touching the Gradio UI.

    ``FileIndex.get_retriever_pipelines`` resolves the selected files through the
    selector widget, which only exists once the UI is built. This mirrors that
    method while passing the selection in directly.

    ``rerank`` pins ``use_reranking`` for the run (A/B of the reranker), leaving the
    app setting alone when it is ``None``.
    """
    prefix = f"index.options.{index.id}."
    stripped = {
        k[len(prefix) :]: v for k, v in settings.items() if k.startswith(prefix)
    }
    if rerank is not None and "use_reranking" in stripped:
        stripped["use_reranking"] = rerank

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
    questions: list[dict],
    retrievers: list[Any],
    doc_ids: list[str],
    corpus: str,
    k: int,
    abstain_threshold: float = 0.0,
    abstain_term_floor: float = 0.0,
) -> list[dict]:
    wanted = normalize_name(corpus)
    results = []
    for question in questions:
        started = time.perf_counter()
        docs = retrieve(retrievers, question["question"], doc_ids)
        elapsed_ms = (time.perf_counter() - started) * 1000
        pages = {str(p) for p in question.get("expect_pages", [])}
        top_score = top_score_of(docs)
        abstain_case = is_abstain_case(question)
        term_evidence = specific_term_evidence(question["question"], docs)

        rank = None
        if not abstain_case:
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
                "category": category_of(question),
                "question": question["question"],
                "expect_pages": sorted(pages),
                "abstain_case": abstain_case,
                "top_score": round(top_score, 3),
                "term_evidence": term_evidence,
                "abstained": should_refuse(
                    scores_of(docs),
                    abstain_threshold,
                    documents=docs,
                    question=question["question"],
                    term_floor=abstain_term_floor,
                ),
                "elapsed_ms": round(elapsed_ms, 1),
                "rank": rank,
                "mrr": 0.0 if rank is None else 1.0 / (rank + 1),
                "terms_ok": (not missing) and not abstain_case,
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
    # latency covers every question (a no-answer question costs a retrieval too)
    latencies = [r.get("elapsed_ms", 0.0) for r in results]
    # a no-answer question has no page to hit; counting it here would drag the
    # retrieval metrics down for doing the right thing (refusing)
    results = [r for r in results if not r.get("abstain_case")]

    def hit(at: int) -> float:
        if not results:
            return 0.0
        return sum(
            1 for r in results if r["rank"] is not None and r["rank"] < at
        ) / len(results)

    return {
        "questions": len(results),
        "corpus_chunks": corpus_chunks,
        "hit_at_1": hit(1),
        "hit_at_3": hit(3),
        "hit_at_5": hit(5),
        "mrr": statistics.fmean([r["mrr"] for r in results]) if results else 0.0,
        "facts": (
            sum(1 for r in results if r["terms_ok"]) / len(results) if results else 0.0
        ),
        "latency_p50_ms": round(percentile(latencies, 0.5), 1),
        "latency_p95_ms": round(percentile(latencies, 0.95), 1),
        "k": k,
    }


def abstain_summary(
    results: list[dict], threshold: float, term_floor: float = 0.0
) -> dict:
    """How the refusal gate would behave at ``threshold``.

    ``abstain_rate`` — share of no-answer questions the gate refuses (higher is better).
    ``false_reject`` — share of answerable questions the gate would *also* refuse
    (lower is better). Both are recomputed from the stored scores, so several
    thresholds can be compared without running retrieval again.

    ``term_floor`` mirrors the app: a question whose *rare entity term* appears in a
    retrieved chunk is answered when the best score reaches this floor, even below the
    threshold (a dense table row answers at a low similarity, MODIFICATIONS §5.8).
    """
    abstain_cases = [r for r in results if r.get("abstain_case")]
    answerable = [r for r in results if not r.get("abstain_case")]

    def refuses(result: dict) -> bool:
        scores = [a.get("score", 0.0) for a in result.get("retrieved") or []]
        if not should_refuse(scores, threshold):
            return False
        if term_floor <= 0 or not result.get("term_evidence"):
            return True
        best = best_similarity(scores)
        return best is None or best < term_floor

    return {
        "threshold": threshold,
        "term_floor": term_floor,
        "abstain_questions": len(abstain_cases),
        "abstain_rate": (
            sum(1 for r in abstain_cases if refuses(r)) / len(abstain_cases)
            if abstain_cases
            else None
        ),
        "false_reject_rate": (
            sum(1 for r in answerable if refuses(r)) / len(answerable)
            if answerable
            else None
        ),
    }


def summarize_by_category(
    results: list[dict], k: int, corpus_chunks: int
) -> dict[str, dict]:
    """Per-category metrics, in a stable order.

    A single overall number hides which questions a change moves: adding a reranker
    can lift ``T1`` while breaking ``T2`` numeric lookups. Categories with no
    questions are absent, so a set without ``category`` yields one entry.
    """
    by_category: dict[str, list[dict]] = {}
    for result in results:
        by_category.setdefault(result.get("category") or DEFAULT_CATEGORY, []).append(
            result
        )
    return {
        name: summarize(items, k, corpus_chunks)
        for name, items in sorted(by_category.items())
    }


def exit_code(summary: dict, fail_under_hit1: float | None) -> int:
    """0 when the run counts as a pass, 1 when the Hit@1 gate is missed.

    A completed run is not a failure: the baseline sits around 60%, so only an
    explicit ``--fail-under-hit1`` turns the metric into a gate.
    """
    if fail_under_hit1 is None:
        return 0
    return 0 if summary["hit_at_1"] >= fail_under_hit1 else 1


def _metrics_row(name: str, summary: dict) -> str:
    return (
        "| {name} | {n} | **{h1:.1%}** | {h3:.1%} | {h5:.1%} | **{mrr:.3f}** "
        "| {facts:.1%} |".format(
            name=name,
            n=summary["questions"],
            h1=summary["hit_at_1"],
            h3=summary["hit_at_3"],
            h5=summary["hit_at_5"],
            mrr=summary["mrr"],
            facts=summary["facts"],
        )
    )


_METRICS_HEADER = (
    "| 类别 | 题数 | Hit@1 | Hit@3 | Hit@5 | MRR | 事实覆盖 |",
    "|---|---|---|---|---|---|---|",
)


def _abstain_lines(abstain: dict | None) -> list[str]:
    """Report lines for the refusal gate.

    Printed for a no-answer set (how many were refused) and for an answerable set
    (how many would have been refused by mistake), so an A/B on the threshold shows
    both sides of the trade-off.
    """
    if not abstain:
        return []
    has_abstain = bool(abstain.get("abstain_questions"))
    false_reject = abstain.get("false_reject_rate")
    if not has_abstain and false_reject is None:
        return []

    parts = [f"拒答闸门（阈值 {abstain['threshold']:.2f}）"]
    if has_abstain:
        parts.append(
            f"无答案题 {abstain['abstain_questions']} 题，"
            f"正确拒答 {abstain['abstain_rate']:.1%}"
        )
    if false_reject is not None:
        parts.append(f"可答题误拒 {false_reject:.1%}")
    return ["；".join(parts)]


def console_report(
    name: str,
    summary: dict,
    results: list[dict],
    categories: dict | None = None,
    abstain: dict | None = None,
) -> None:
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
    print(
        f"检索耗时 P50 = {summary['latency_p50_ms']:.1f} ms   "
        f"P95 = {summary['latency_p95_ms']:.1f} ms（每题一次检索，含重排）"
    )

    if categories and len(categories) > 1:
        print()
        print("按类别（一个总数字会掩盖某一类变好、另一类变坏）：")
        row_template = (
            "  {name:<6} n={n:<4} Hit@1={h1:>6.1%}  MRR={mrr:.3f}  事实={facts:>6.1%}"
        )
        for category, category_summary in categories.items():
            print(
                row_template.format(
                    name=category,
                    n=category_summary["questions"],
                    h1=category_summary["hit_at_1"],
                    mrr=category_summary["mrr"],
                    facts=category_summary["facts"],
                )
            )

    for line in _abstain_lines(abstain):
        print(line)


def markdown_report(
    name: str,
    summary: dict,
    results: list[dict],
    categories: dict | None = None,
    abstain: dict | None = None,
) -> str:
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
        f"| 检索耗时 P50 | {summary['latency_p50_ms']:.1f} ms |",
        f"| 检索耗时 P95 | {summary['latency_p95_ms']:.1f} ms |",
        "",
    ]
    if categories and len(categories) > 1:
        lines += ["#### 按类别", "", *_METRICS_HEADER]
        lines += [_metrics_row(cat, s) for cat, s in categories.items()]
        lines += ["", *_METRICS_HEADER]
        lines += [_metrics_row("全部", summary)]
        lines += [""]

    for line in _abstain_lines(abstain):
        lines += [line, ""]

    lines += [
        "<details><summary>逐题明细</summary>",
        "",
        "| # | 类别 | 问题 | 期望页 | 命中名次 | 关键事实 |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        if r.get("abstain_case"):
            rank = "应拒答" if r.get("abstained") else "未拒答"
            terms = "✅" if r.get("abstained") else "❌ 硬答"
        else:
            rank = "未命中" if r["rank"] is None else r["rank"] + 1
            terms = "✅" if r["terms_ok"] else "❌ " + "、".join(r["missing_terms"])
        lines.append(
            "| {id} | {cat} | {q} | {pages} | {rank} | {terms} |".format(
                id=r["id"],
                cat=r.get("category", DEFAULT_CATEGORY),
                q=r["question"].replace("|", "\\|"),
                pages="/".join(r["expect_pages"]) or "-",
                rank=rank,
                terms=terms,
            )
        )
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval", required=True, help="path to the evaluation set")
    parser.add_argument(
        "--top-k", type=int, default=5, help="window for fact checking (default: 5)"
    )
    parser.add_argument("--index-id", type=int, default=None, help="file index to use")
    parser.add_argument(
        "--user-id", default=None, help="owner of the corpus (default: detected)"
    )
    parser.add_argument(
        "--corpus",
        default=None,
        help="corpus file name to score against (default: the one in the eval set)",
    )
    parser.add_argument(
        "--category",
        default=None,
        help=f"score one category only (e.g. T2; unlabeled questions count as "
        f"'{DEFAULT_CATEGORY}')",
    )
    parser.add_argument(
        "--rerank",
        choices=("on", "off"),
        default=None,
        help="pin the reranker for an A/B run (default: keep the app setting)",
    )
    parser.add_argument(
        "--scope",
        default=None,
        help=(
            "restrict retrieval to the file(s) whose name contains this string "
            "(the app's 'search in file(s)' mode); default: every indexed file"
        ),
    )
    parser.add_argument(
        "--fail-under-hit1",
        type=float,
        default=None,
        metavar="RATIO",
        help="exit 1 when Hit@1 is below this ratio (default: no gate)",
    )
    parser.add_argument(
        "--abstain-threshold",
        type=float,
        default=None,
        metavar="SCORE",
        help=(
            "score below which the chat gate refuses to answer (default: "
            "KH_ABSTAIN_SCORE_THRESHOLD from the config); only affects sets that "
            "carry no-answer questions"
        ),
    )
    parser.add_argument(
        "--abstain-term-floor",
        type=float,
        default=None,
        metavar="SCORE",
        help=(
            "with a rare entity term in the retrieved chunks, answer down to this "
            "score (default: KH_ABSTAIN_TERM_FLOOR; 0 disables the override)"
        ),
    )
    parser.add_argument("--out", default=None, help="write a Markdown report here")
    parser.add_argument(
        "--json", dest="json_out", default=None, help="write raw results here"
    )
    args = parser.parse_args(argv)

    eval_set = load_eval_set(Path(args.eval))
    corpus = args.corpus or eval_set.get("corpus", "")
    questions = eval_set["questions"]
    if args.category:
        wanted = args.category.casefold()
        questions = [q for q in questions if category_of(q).casefold() == wanted]
        if not questions:
            categories = sorted({category_of(q) for q in eval_set["questions"]})
            print(
                f"no question in category {args.category!r}; available: "
                f"{', '.join(categories)}"
            )
            return 2

    print(f"evaluation set: {eval_set.get('name', args.eval)}")
    print(f"corpus        : {corpus or '(any indexed file)'}")
    print(f"questions     : {len(questions)}")
    if args.category:
        print(f"category      : {args.category}")

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
    if args.scope:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from ktem.db.models import engine

        Source = index._resources["Source"]
        statement = select(Source.id, Source.name)
        if index.config.get("private", False):
            statement = statement.where(Source.user == user_id)
        with Session(engine) as session:
            rows = [(row[0], row[1]) for row in session.execute(statement).all()]
        doc_ids = pick_doc_ids(rows, args.scope)
        print(f"scope         : {args.scope} → {len(doc_ids)} file(s)")
        if not doc_ids:
            print("no indexed file matches --scope")
            return 2
    print(f"files in scope: {len(doc_ids)}")
    if not doc_ids:
        print("no file is indexed for this user — upload the corpus first")
        return 2

    rerank = None if args.rerank is None else args.rerank == "on"
    retrievers = build_retrievers(index, settings, user_id, doc_ids, rerank=rerank)
    print(f"retrievers    : {', '.join(type(r).__name__ for r in retrievers)}")
    if args.rerank is not None:
        print(f"rerank        : {args.rerank} (pinned for this run)")

    from theflow.settings import settings as flowsettings

    abstain_threshold = (
        args.abstain_threshold
        if args.abstain_threshold is not None
        else float(getattr(flowsettings, "KH_ABSTAIN_SCORE_THRESHOLD", 0.0) or 0.0)
    )
    abstain_term_floor = (
        args.abstain_term_floor
        if args.abstain_term_floor is not None
        else float(getattr(flowsettings, "KH_ABSTAIN_TERM_FLOOR", 0.0) or 0.0)
    )
    print(f"abstain gate  : score < {abstain_threshold:.2f} refuses "
          f"(rare entity term may answer down to {abstain_term_floor:.2f})")

    # how many chunks the corpus actually contributes, i.e. the ceiling of Hit@k
    corpus_chunks = 0
    probe = retrieve(retrievers, corpus, doc_ids) if corpus else []
    corpus_chunks = sum(
        1
        for d in probe
        if normalize_name((getattr(d, "metadata", {}) or {}).get("file_name"))
        == normalize_name(corpus)
    )

    results = evaluate(
        questions,
        retrievers,
        doc_ids,
        corpus,
        args.top_k,
        abstain_threshold,
        abstain_term_floor,
    )
    summary = summarize(results, args.top_k, corpus_chunks)
    categories = summarize_by_category(results, args.top_k, corpus_chunks)
    abstain = abstain_summary(results, abstain_threshold, abstain_term_floor)
    console_report(
        eval_set.get("name", args.eval), summary, results, categories, abstain
    )

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            markdown_report(
                eval_set.get("name", args.eval),
                summary,
                results,
                categories,
                abstain,
            ),
            encoding="utf-8",
        )
        print(f"markdown report -> {args.out}")
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(
                {
                    "summary": summary,
                    "categories": categories,
                    "abstain": abstain,
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"raw results     -> {args.json_out}")

    code = exit_code(summary, args.fail_under_hit1)
    if code:
        print(
            f"\nFAIL: Hit@1 {summary['hit_at_1']:.1%} < threshold "
            f"{args.fail_under_hit1:.1%}"
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
