/**
 * Minimal Server-Sent-Events parser.
 *
 * `EventSource` cannot POST, and the chat endpoint is a POST with a JSON body, so
 * the stream is read with `fetch` + `ReadableStream` and parsed here. Keeping the
 * parser free of React/DOM code is what makes it testable (`sse.test.ts`): the
 * important cases are a JSON payload split across two TCP chunks, several events
 * in one chunk, `\r\n` line endings, multi-line `data:` and comments.
 */

export interface SseEvent {
  event: string;
  data: string;
}

export interface SseParser {
  /** Feed a decoded chunk; complete events are dispatched synchronously. */
  push(chunk: string): void;
  /** Dispatch a trailing event that did not end with a blank line. */
  flush(): void;
}

export function createSseParser(onEvent: (event: SseEvent) => void): SseParser {
  let buffer = "";

  const dispatch = (raw: string): void => {
    let event = "message";
    const data: string[] = [];

    for (const line of raw.split("\n")) {
      if (!line || line.startsWith(":")) continue;
      const colon = line.indexOf(":");
      const field = colon === -1 ? line : line.slice(0, colon);
      let value = colon === -1 ? "" : line.slice(colon + 1);
      if (value.startsWith(" ")) value = value.slice(1);

      if (field === "event") event = value;
      else if (field === "data") data.push(value);
    }

    if (data.length > 0) onEvent({ event, data: data.join("\n") });
  };

  return {
    push(chunk: string): void {
      // SSE allows CRLF, LF and lone CR. Normalising to LF keeps the split logic
      // simple and still handles a chunk boundary between "\r" and "\n".
      buffer += chunk.replace(/\r\n/g, "\n").replace(/\r(?!\n)/g, "\n");

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const raw = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        dispatch(raw);
        boundary = buffer.indexOf("\n\n");
      }
    },
    flush(): void {
      if (buffer.trim()) {
        dispatch(buffer);
        buffer = "";
      }
    },
  };
}

/** Convenience wrapper for tests and for one-shot streamed strings. */
export function parseSseString(input: string): SseEvent[] {
  const events: SseEvent[] = [];
  const parser = createSseParser((event) => events.push(event));
  parser.push(input);
  parser.flush();
  return events;
}

/** A parsed event whose `data` is JSON, or `null` when it is not valid JSON. */
export function parseJsonData<T>(data: string): T | null {
  try {
    return JSON.parse(data) as T;
  } catch {
    return null;
  }
}

/**
 * Read one `text/event-stream` response from `fetch` and dispatch its events.
 *
 * `EventSource` cannot send a POST body or a `FormData` body, so both the chat
 * endpoint (JSON POST) and the file endpoints (multipart upload, bare POST for
 * reindex) use this instead. The reader is always released, including when the
 * caller aborts the request: the abort surfaces as a rejection from
 * `reader.read()`, which propagates to the caller.
 */
export async function readSse(
  response: Response,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  if (!response.body) {
    throw new Error("the response has no body to stream");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser(onEvent);

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }
    parser.push(decoder.decode());
    parser.flush();
  } finally {
    reader.releaseLock();
  }
}
