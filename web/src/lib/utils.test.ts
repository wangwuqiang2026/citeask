import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type { ConversationSummary } from "./types.ts";
import {
  groupConversations,
  isRelevantEvidence,
  legacyFileUrl,
  relevancePercent,
  shouldSubmitOnEnter,
} from "./utils.ts";

function conversation(id: string, date: string): ConversationSummary {
  return {
    id,
    name: id,
    is_public: false,
    date_created: date,
    date_updated: date,
    preview: null,
  };
}

describe("groupConversations", () => {
  const now = new Date("2026-10-18T12:00:00Z");

  it("buckets by today / yesterday / last 7 days / earlier", () => {
    const groups = groupConversations(
      [
        conversation("today", "2026-10-18T08:00:00Z"),
        conversation("yesterday", "2026-10-17T08:00:00Z"),
        conversation("week", "2026-10-14T08:00:00Z"),
        conversation("old", "2026-09-01T08:00:00Z"),
      ],
      now,
    );

    assert.deepEqual(
      groups.map((group) => group.key),
      ["date.today", "date.yesterday", "date.previous7", "date.earlier"],
    );
    assert.deepEqual(
      groups.flatMap((group) => group.items.map((item) => item.id)),
      ["today", "yesterday", "week", "old"],
    );
  });

  it("drops empty buckets and keeps unparsable dates in 'earlier'", () => {
    const groups = groupConversations(
      [conversation("broken", "not-a-date"), conversation("today", "2026-10-18T01:00:00Z")],
      now,
    );

    assert.deepEqual(
      groups.map((group) => group.key),
      ["date.today", "date.earlier"],
    );
  });
});

describe("legacyFileUrl", () => {
  it("URL-encodes a native path and appends the page anchor", () => {
    assert.equal(
      legacyFileUrl("C:\\data\\a b.pdf", 3),
      "/legacy/file=C%3A%5Cdata%5Ca%20b.pdf#page=3",
    );
  });

  it("falls back to the classic root without a path", () => {
    assert.equal(legacyFileUrl(null, 2), "/legacy");
  });
});

describe("relevancePercent", () => {
  it("prefers the rerank score, then the general score, and clamps", () => {
    assert.equal(relevancePercent({ rerank_score: 0.82, score: 0.1 }), 82);
    assert.equal(relevancePercent({ score: 0.5 }), 50);
    assert.equal(relevancePercent({ rerank_score: 3 }), 100);
    assert.equal(relevancePercent({ score: -2 }), 0);
  });
});

describe("isRelevantEvidence", () => {
  it("keeps cited evidence", () => {
    assert.equal(isRelevantEvidence({ cited: true }), true);
  });

  it("keeps entity-row hits the answer did not cite", () => {
    assert.equal(isRelevantEvidence({ cited: false, entity_row: true }), true);
  });

  it("drops an ordinary uncited vector candidate", () => {
    assert.equal(
      isRelevantEvidence({ cited: false, entity_row: false, vector_score: 0.35 }),
      false,
    );
  });

  it("falls back to NO_SIMILARITY for conversations stored before entity_row", () => {
    // The entity-row / full-text passes are the only sources of -1.0 chunks.
    assert.equal(isRelevantEvidence({ cited: false, vector_score: -1 }), true);
    assert.equal(isRelevantEvidence({ cited: false, vector_score: 0.35 }), false);
  });

  it("trusts the explicit flag once the payload has it", () => {
    // A full-text-only hit in a new payload is not an entity row and stays a candidate.
    assert.equal(
      isRelevantEvidence({ cited: false, entity_row: false, vector_score: -1 }),
      false,
    );
  });
});

describe("shouldSubmitOnEnter", () => {
  it("submits on a plain Enter", () => {
    assert.equal(shouldSubmitOnEnter({ key: "Enter" }), true);
    assert.equal(shouldSubmitOnEnter({ key: "Enter", shiftKey: false }), true);
  });

  it("does not submit on Shift+Enter or any other key", () => {
    assert.equal(shouldSubmitOnEnter({ key: "Enter", shiftKey: true }), false);
    assert.equal(shouldSubmitOnEnter({ key: "a" }), false);
    assert.equal(shouldSubmitOnEnter({ key: "Escape" }), false);
  });

  it("keeps Ctrl/Meta+Enter as a send shortcut, as the old onKeyDown did", () => {
    assert.equal(shouldSubmitOnEnter({ key: "Enter", ctrlKey: true }), true);
    assert.equal(shouldSubmitOnEnter({ key: "Enter", metaKey: true }), true);
    // The old first branch did not look at Shift, so Ctrl+Shift+Enter also sent.
    assert.equal(shouldSubmitOnEnter({ key: "Enter", ctrlKey: true, shiftKey: true }), true);
  });

  it("never submits while an IME is composing", () => {
    assert.equal(shouldSubmitOnEnter({ key: "Enter", isComposing: true }), false);
    // Safari reports the 229 sentinel instead of isComposing.
    assert.equal(shouldSubmitOnEnter({ key: "Enter", keyCode: 229 }), false);
    assert.equal(
      shouldSubmitOnEnter({ key: "Enter", keyCode: 229, ctrlKey: true }),
      false,
    );
  });
});
