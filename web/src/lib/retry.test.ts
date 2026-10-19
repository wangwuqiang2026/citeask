import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { shouldRetry } from "./retry.ts";

class FakeApiError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`HTTP ${status}`);
    this.status = status;
  }
}

describe("query retry policy", () => {
  it("never retries a 4xx: the same request cannot succeed again", () => {
    for (const status of [400, 401, 403, 404, 422]) {
      assert.equal(shouldRetry(0, new FakeApiError(status)), false);
    }
  });

  it("retries a server or network failure once", () => {
    assert.equal(shouldRetry(0, new FakeApiError(500)), true);
    assert.equal(shouldRetry(0, new TypeError("Failed to fetch")), true);
    assert.equal(shouldRetry(1, new FakeApiError(500)), false);
  });

  it("treats an error without a numeric status as transient", () => {
    assert.equal(shouldRetry(0, { status: "401" }), true);
    assert.equal(shouldRetry(0, null), true);
  });
});
