/**
 * Citation markers inside an answer.
 *
 * The classic UI renders `【n】` markers in the answer body and links them to the
 * n-th item of the evidence list. The renderer therefore splits the plain text
 * children of a paragraph into text and citation tokens instead of touching the
 * markdown source (which would break tables/lists).
 */

export type InlineToken =
  | { type: "text"; value: string }
  | { type: "citation"; index: number };

/** `【n】` is the documented marker; `[n]` is accepted for older answers. */
const CITATION_PATTERN = /【(\d+)】|\[(\d+)\]/g;

export function splitCitations(text: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let lastIndex = 0;

  for (const match of text.matchAll(CITATION_PATTERN)) {
    const start = match.index ?? 0;
    const marker = match[0];
    const raw = match[1] ?? match[2];
    if (start > lastIndex) {
      tokens.push({ type: "text", value: text.slice(lastIndex, start) });
    }
    // 1-based in the answer, 0-based in the evidence array.
    const index = Number.parseInt(raw, 10) - 1;
    if (Number.isFinite(index) && index >= 0) {
      tokens.push({ type: "citation", index });
    } else {
      tokens.push({ type: "text", value: marker });
    }
    lastIndex = start + marker.length;
  }

  if (lastIndex < text.length) {
    tokens.push({ type: "text", value: text.slice(lastIndex) });
  }
  return tokens;
}

/** The text of an answer without its citation markers (copy/plain view). */
export function stripCitations(text: string): string {
  return text.replace(CITATION_PATTERN, "").trim();
}
