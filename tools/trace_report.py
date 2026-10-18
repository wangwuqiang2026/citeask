#!/usr/bin/env python
"""Aggregate the per-query trace written by the chat pipeline.

The chat pipeline appends one JSON line per question when ``KH_QUERY_TRACE`` is set
(see ``ktem/utils/trace.py``): retrieved count, best similarity, whether the refusal
gate fired, answer length, wall-clock time, and the LLM usage that request consumed.
This tool turns that file into the numbers a comparison needs — answer latency, token
cost, refusal rate — which is how a switch such as ``use_llm_reranking`` gets measured
instead of guessed (ROADMAP C3/C4).

    python tools/trace_report.py                      # default trace location
    python tools/trace_report.py --trace path.jsonl --last 20 --json report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]


def summarize_trace(entries: list[dict]) -> dict:
    """Aggregate trace entries into one comparison table."""
    from tools.eval_retrieval import percentile

    if not entries:
        return {
            "requests": 0,
            "abstained": 0,
            "abstain_rate": 0.0,
            "latency_p50_ms": 0.0,
            "latency_p95_ms": 0.0,
            "total_tokens": 0,
            "avg_tokens": 0.0,
            "avg_llm_calls": 0.0,
            "avg_retrieved": 0.0,
            "reranked_rate": 0.0,
        }

    def numeric(key: str) -> list[float]:
        return [float(entry.get(key) or 0.0) for entry in entries]

    requests = len(entries)
    abstained = sum(1 for entry in entries if entry.get("abstained"))
    return {
        "requests": requests,
        "abstained": abstained,
        "abstain_rate": abstained / requests,
        "latency_p50_ms": round(percentile(numeric("total_ms"), 0.5), 1),
        "latency_p95_ms": round(percentile(numeric("total_ms"), 0.95), 1),
        "total_tokens": int(sum(numeric("total_tokens"))),
        "avg_tokens": round(sum(numeric("total_tokens")) / requests, 1),
        "avg_llm_calls": round(sum(numeric("calls")) / requests, 1),
        "avg_retrieved": round(sum(numeric("retrieved")) / requests, 1),
        "reranked_rate": sum(1 for entry in entries if entry.get("reranked"))
        / requests,
    }


def render(summary: dict) -> str:
    return "\n".join(
        [
            "| 指标 | 值 |",
            "|---|---|",
            f"| 请求数 | {summary['requests']} |",
            f"| 拒答 | {summary['abstained']}（{summary['abstain_rate']:.1%}） |",
            f"| 端到端 P50 / P95 | {summary['latency_p50_ms']:.0f} / "
            f"{summary['latency_p95_ms']:.0f} ms |",
            f"| 每题 token（合计） | {summary['avg_tokens']:.0f}"
            f"（{summary['total_tokens']}） |",
            f"| 每题 LLM 调用数 | {summary['avg_llm_calls']:.1f} |",
            f"| 每题召回块数 | {summary['avg_retrieved']:.1f} |",
            f"| 启用重排的比例 | {summary['reranked_rate']:.1%} |",
        ]
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trace",
        default=None,
        help="trace file (default: KH_QUERY_TRACE / ktem_app_data/query_trace.jsonl)",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=0,
        help="only the last N entries (0 = all; useful for A/B runs kept in one file)",
    )
    parser.add_argument(
        "--json", dest="json_out", default=None, help="write the summary"
    )
    args = parser.parse_args(argv)

    for lib in ("libs/ktem", "libs/kotaemon"):
        sys.path.insert(0, str(REPO_ROOT / lib))
    sys.path.insert(0, str(REPO_ROOT))

    from ktem.utils.trace import read_trace, trace_path

    path = Path(args.trace) if args.trace else trace_path()
    if path is None:
        print("tracing is off: set KH_QUERY_TRACE=1 (or a path) and ask a question")
        return 2

    entries = read_trace(path)
    if args.last > 0:
        entries = entries[-args.last :]
    if not entries:
        print(f"no trace entries in {path}")
        return 2

    summary = summarize_trace(entries)
    print(f"trace: {path}（{len(entries)} 条）")
    print(render(summary))

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nsummary -> {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
