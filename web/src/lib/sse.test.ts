import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createSseParser, parseJsonData, parseSseString, readSse } from "./sse.ts";

describe("SSE parser", () => {
  it("dispatches one event per blank line", () => {
    const events = parseSseString(
      'event: start\ndata: {"message_id":"m1"}\n\nevent: token\ndata: {"delta":"你"}\n\n',
    );

    assert.equal(events.length, 2);
    assert.deepEqual(events[0], { event: "start", data: '{"message_id":"m1"}' });
    assert.deepEqual(events[1], { event: "token", data: '{"delta":"你"}' });
  });

  it("reassembles an event split across two chunks", () => {
    const events: { event: string; data: string }[] = [];
    const parser = createSseParser((event) => events.push(event));

    parser.push('event: token\ndata: {"del');
    assert.equal(events.length, 0);
    parser.push('ta":"half"}\n\n');

    assert.deepEqual(events, [{ event: "token", data: '{"delta":"half"}' }]);
  });

  it("handles CRLF and several events in one chunk", () => {
    const events = parseSseString('event: a\r\ndata: 1\r\n\r\nevent: b\r\ndata: 2\r\n\r\n');

    assert.deepEqual(events, [
      { event: "a", data: "1" },
      { event: "b", data: "2" },
    ]);
  });

  it("joins multi-line data with a newline", () => {
    const events = parseSseString("data: line one\ndata: line two\n\n");
    assert.deepEqual(events[0], { event: "message", data: "line one\nline two" });
  });

  it("ignores comments and keeps the default event name", () => {
    const events = parseSseString(": keep-alive\ndata: value\n\n");
    assert.deepEqual(events[0], { event: "message", data: "value" });
  });

  it("flushes a trailing event without a blank line", () => {
    const events = parseSseString('event: done\ndata: {"message_id":"m"}');
    assert.deepEqual(events, [{ event: "done", data: '{"message_id":"m"}' }]);
  });

  it("parses JSON payloads and tolerates invalid ones", () => {
    assert.deepEqual(parseJsonData<{ delta: string }>('{"delta":"x"}'), { delta: "x" });
    assert.equal(parseJsonData("not json"), null);
  });
});

/** A Response whose body arrives in the given chunks, like a real stream. */
function streamedResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream);
}

describe("readSse", () => {
  it("dispatches the events of a response split across chunks", async () => {
    const events: { event: string; data: string }[] = [];
    await readSse(
      streamedResponse(['event: progress\ndata: {"line":"a"}\n\nevent: do', 'ne\ndata: {"ids":[]}\n\n']),
      (event) => events.push(event),
    );

    assert.deepEqual(events, [
      { event: "progress", data: '{"line":"a"}' },
      { event: "done", data: '{"ids":[]}' },
    ]);
  });

  it("rejects a response without a body", async () => {
    await assert.rejects(() => readSse(new Response(null), () => {}));
  });
});
