"""Tests for the query trace (``ktem/utils/trace.py``), usage accounting and the report.

The trace is what makes "what did this answer cost" answerable (ROADMAP C3/C4), so its
recording, its failure mode (a trace must never break an answer) and the aggregation
are pinned here.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

from ktem.utils import trace as trace_module
from ktem.utils.trace import TraceRecorder, read_trace
from kotaemon.llms.usage import UsageCounter
from tools.trace_report import render, summarize_trace


@pytest.fixture
def workdir():
    """Scratch directory (Path.mkdir, not mkdtemp: 0o700 dirs are not writable here)."""
    path = Path(tempfile.gettempdir()) / f"trace-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# --------------------------------------------------------------------------- #
# usage accounting
# --------------------------------------------------------------------------- #
def test_usage_counter_accumulates_and_reports_deltas():
    counter = UsageCounter()
    before = counter.snapshot()

    counter.add(prompt_tokens=100, completion_tokens=20, total=120)
    counter.add(prompt_tokens=50, completion_tokens=10, total=60)

    assert counter.snapshot() == {
        "calls": 2,
        "prompt_tokens": 150,
        "completion_tokens": 30,
        "total_tokens": 180,
    }
    assert counter.since(before) == {
        "calls": 2,
        "prompt_tokens": 150,
        "completion_tokens": 30,
        "total_tokens": 180,
    }
    assert counter.since(counter.snapshot())["calls"] == 0


def test_usage_counter_reset_clears_everything():
    counter = UsageCounter()
    counter.add(prompt_tokens=10, completion_tokens=5, total=15)

    counter.reset()

    assert counter.snapshot()["total_tokens"] == 0


def test_streaming_usage_blocks_are_recorded():
    """A streaming answer only reports usage in its final chunk (that is why the
    wrapper asks for ``stream_options``); the recorder must accept that shape."""
    from kotaemon.llms.chats.openai import BaseChatOpenAI
    from kotaemon.llms.usage import usage

    usage.reset()
    BaseChatOpenAI._record_usage(None)
    BaseChatOpenAI._record_usage(
        {"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": 42}
    )

    assert usage.snapshot() == {
        "calls": 1,
        "prompt_tokens": 30,
        "completion_tokens": 12,
        "total_tokens": 42,
    }
    usage.reset()


# --------------------------------------------------------------------------- #
# the recorder
# --------------------------------------------------------------------------- #
def test_a_recorder_without_a_path_is_disabled_and_writes_nothing():
    recorder = TraceRecorder(path=None)

    assert recorder.enabled is False
    assert recorder.record(question="q") is None


def test_a_recorder_appends_one_json_line_per_query(workdir):
    path = workdir / "trace.jsonl"
    recorder = TraceRecorder(path=path)

    first = recorder.record(question="q1", retrieved=3, total_ms=12.5)
    recorder.record(question="q2", abstained=True)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["question"] == "q1"
    assert first["question"] == "q1"
    assert first["time"]


def test_a_trace_write_failure_never_breaks_the_answer(workdir):
    blocked = workdir / "file.txt"
    blocked.write_text("not a directory", encoding="utf-8")

    recorder = TraceRecorder(path=blocked / "trace.jsonl")

    assert recorder.record(question="q") is None  # returns quietly


def test_read_trace_skips_malformed_lines(workdir):
    path = workdir / "trace.jsonl"
    path.write_text(
        '{"question": "ok"}\nnot json\n\n{"question": "second"}\n', encoding="utf-8"
    )

    assert [entry["question"] for entry in read_trace(path)] == ["ok", "second"]


def test_read_trace_of_a_missing_file_is_empty(workdir):
    assert read_trace(workdir / "nope.jsonl") == []


def test_the_trace_path_comes_from_the_configuration(monkeypatch, workdir):
    monkeypatch.setattr(trace_module.flowsettings, "KH_APP_DATA_DIR", workdir)

    monkeypatch.setattr(trace_module.flowsettings, "KH_QUERY_TRACE", "")
    assert trace_module.trace_path() is None

    monkeypatch.setattr(trace_module.flowsettings, "KH_QUERY_TRACE", "1")
    assert trace_module.trace_path() == workdir / "query_trace.jsonl"

    monkeypatch.setattr(trace_module.flowsettings, "KH_QUERY_TRACE", "custom/t.jsonl")
    assert trace_module.trace_path() == Path("custom/t.jsonl")


# --------------------------------------------------------------------------- #
# the report
# --------------------------------------------------------------------------- #
def entry(**kwargs):
    base = {
        "total_ms": 1000.0,
        "total_tokens": 500,
        "calls": 2,
        "retrieved": 5,
        "abstained": False,
        "reranked": True,
    }
    base.update(kwargs)
    return base


def test_summary_of_an_empty_trace_is_zeroed():
    summary = summarize_trace([])

    assert summary["requests"] == 0
    assert summary["abstain_rate"] == 0.0
    assert summary["latency_p50_ms"] == 0.0


def test_summary_aggregates_latency_tokens_and_refusals():
    entries = [
        entry(total_ms=1000.0, total_tokens=500, calls=2),
        entry(total_ms=3000.0, total_tokens=700, calls=4, abstained=True),
        entry(total_ms=2000.0, total_tokens=0, calls=0, abstained=True, reranked=False),
    ]

    summary = summarize_trace(entries)

    assert summary["requests"] == 3
    assert summary["abstained"] == 2
    assert summary["abstain_rate"] == pytest.approx(2 / 3)
    assert summary["latency_p50_ms"] == 2000.0
    assert summary["total_tokens"] == 1200
    assert summary["avg_tokens"] == 400.0
    assert summary["avg_llm_calls"] == 2.0
    assert summary["reranked_rate"] == pytest.approx(2 / 3)


def test_the_rendered_report_keeps_the_numbers_visible():
    text = render(summarize_trace([entry()]))

    assert "请求数" in text
    assert "P50" in text
    assert "500" in text  # total tokens
