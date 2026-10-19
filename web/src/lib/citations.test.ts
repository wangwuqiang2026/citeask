import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { splitCitations, stripCitations } from "./citations.ts";

describe("citation markers", () => {
  it("splits text and 1-based marker positions", () => {
    assert.deepEqual(splitCitations("答案【1】还有【2】"), [
      { type: "text", value: "答案" },
      { type: "citation", index: 0 },
      { type: "text", value: "还有" },
      { type: "citation", index: 1 },
    ]);
  });

  it("accepts the older [n] marker", () => {
    assert.deepEqual(splitCitations("a [3] b"), [
      { type: "text", value: "a " },
      { type: "citation", index: 2 },
      { type: "text", value: " b" },
    ]);
  });

  it("keeps unmatchable markers as text", () => {
    assert.deepEqual(splitCitations("【0】"), [{ type: "text", value: "【0】" }]);
  });

  it("returns no tokens for empty text", () => {
    assert.deepEqual(splitCitations(""), []);
  });

  it("strips markers for plain-text copies", () => {
    assert.equal(stripCitations("结论【1】【2】。"), "结论。");
  });
});
