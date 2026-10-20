import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  buildUploadForm,
  fileKind,
  formatBytes,
  formatTokens,
  isLoaderWarning,
  parseFileRows,
  parseUploadEvent,
} from "./files.ts";

describe("fileKind", () => {
  it("maps the API's type column to a visual kind", () => {
    assert.equal(fileKind("pdf"), "pdf");
    assert.equal(fileKind("docx"), "word");
    assert.equal(fileKind("xls"), "sheet");
    assert.equal(fileKind("pptx"), "slide");
    assert.equal(fileKind("png"), "image");
    assert.equal(fileKind("zip"), "archive");
    assert.equal(fileKind("md"), "text");
    assert.equal(fileKind("py"), "code");
    assert.equal(fileKind("url"), "url");
  });

  it("accepts a full file name and unknown extensions", () => {
    assert.equal(fileKind("奖学金评定办法.PDF"), "pdf");
    assert.equal(fileKind("报告.weird"), "other");
    assert.equal(fileKind(""), "other");
    assert.equal(fileKind(null), "other");
  });
});

describe("formatTokens", () => {
  it("groups digits and keeps the backend's placeholder", () => {
    assert.equal(formatTokens(6983734), "6,983,734");
    assert.equal(formatTokens("2429"), "2,429");
    assert.equal(formatTokens("-"), "-");
    assert.equal(formatTokens(""), "-");
    assert.equal(formatTokens(null), "-");
    assert.equal(formatTokens(Number.NaN), "-");
  });
});

describe("isLoaderWarning", () => {
  it("recognises the warning prefix the backend writes on failures", () => {
    assert.equal(isLoaderWarning("\u26a0 OCR failed"), true);
    assert.equal(isLoaderWarning("DocxReader"), false);
    assert.equal(isLoaderWarning(undefined), false);
  });
});

describe("formatBytes", () => {
  it("scales bytes to a compact human value", () => {
    assert.equal(formatBytes(0), "0 B");
    assert.equal(formatBytes(900), "900 B");
    assert.equal(formatBytes(1536), "1.5 KB");
    assert.equal(formatBytes(9 * 1024 * 1024), "9.0 MB");
    assert.equal(formatBytes(-1), "-");
  });
});

describe("buildUploadForm", () => {
  it("repeats files, keeps the newline list and always sends reindex", () => {
    const form = buildUploadForm({
      files: [
        new File(["a"], "a.txt", { type: "text/plain" }),
        new File(["b"], "b.txt", { type: "text/plain" }),
      ],
      urls: "https://example.com/a\n\nhttps://example.com/b\n",
      indexId: 1,
      reindex: true,
    });

    assert.equal(form.getAll("files").length, 2);
    assert.equal((form.get("files") as File).name, "a.txt");
    assert.equal(form.get("urls"), "https://example.com/a\n\nhttps://example.com/b");
    assert.equal(form.get("index_id"), "1");
    assert.equal(form.get("reindex"), "true");
  });

  it("omits index_id and urls when they are empty", () => {
    const form = buildUploadForm({ files: [], urls: "   ", reindex: false });

    assert.equal(form.get("index_id"), null);
    assert.equal(form.get("urls"), null);
    assert.equal(form.get("reindex"), "false");
  });
});

describe("parseFileRows", () => {
  it("parses the /files response shape: {rows} with file_id/name columns", () => {
    assert.deepEqual(
      parseFileRows({
        index_id: "1",
        columns: ["file_id", "name"],
        rows: [
          { file_id: "a", name: "a.pdf" },
          { file_id: "b", name: "b.docx" },
        ],
      }),
      [
        { id: "a", file_name: "a.pdf" },
        { id: "b", file_name: "b.docx" },
      ],
    );
  });

  it("also accepts a bare array and the legacy {items} envelope", () => {
    assert.deepEqual(parseFileRows([{ id: "x", file_name: "x.txt" }]), [
      { id: "x", file_name: "x.txt" },
    ]);
    assert.deepEqual(parseFileRows({ items: [{ id: "y", name: "y.txt" }] }), [
      { id: "y", file_name: "y.txt" },
    ]);
  });

  it("maps the id/name aliases and falls back to the id as the name", () => {
    assert.deepEqual(
      parseFileRows({
        rows: [
          { id: "1", filename: "one.pdf" },
          { file_id: "2", file_name: "two.pdf" },
          { file_id: "3" },
        ],
      }),
      [
        { id: "1", file_name: "one.pdf" },
        { id: "2", file_name: "two.pdf" },
        { id: "3", file_name: "3" },
      ],
    );
  });

  it("drops rows without an id and returns [] for unknown payloads", () => {
    assert.deepEqual(
      parseFileRows({ rows: [{ name: "no-id.pdf" }, null, { file_id: "keep" }] }),
      [{ id: "keep", file_name: "keep" }],
    );
    assert.deepEqual(parseFileRows(null), []);
    assert.deepEqual(parseFileRows({ rows: "nope" }), []);
    assert.deepEqual(parseFileRows({ unexpected: [] }), []);
  });
});

describe("parseUploadEvent", () => {
  it("parses the three documented frames", () => {
    assert.deepEqual(
      parseUploadEvent({ event: "progress", data: '{"line":"✅ | a.pdf"}' }),
      { type: "progress", line: "✅ | a.pdf" },
    );
    assert.deepEqual(
      parseUploadEvent({ event: "done", data: '{"ids":["x"],"errors":[]}' }),
      { type: "done", ids: ["x"], errors: [] },
    );
    assert.deepEqual(
      parseUploadEvent({ event: "error", data: '{"message":"索引失败"}' }),
      { type: "error", message: "索引失败" },
    );
  });

  it("ignores unknown frames and malformed payloads", () => {
    assert.equal(parseUploadEvent({ event: "token", data: "{}" }), null);
    assert.equal(parseUploadEvent({ event: "progress", data: "oops" }), null);
    assert.equal(parseUploadEvent({ event: "done", data: "nope" }), null);
  });

  it("coerces non-string ids and keeps a non-JSON error readable", () => {
    assert.deepEqual(parseUploadEvent({ event: "done", data: '{"ids":[1,2]}' }), {
      type: "done",
      ids: ["1", "2"],
      errors: [],
    });
    assert.deepEqual(parseUploadEvent({ event: "error", data: "plain failure" }), {
      type: "error",
      message: "plain failure",
    });
  });
});
