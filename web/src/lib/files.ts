import type { SseEvent } from "./sse";

/**
 * Pure helpers of the file page: type detection, number formatting, the upload
 * payload and the upload/reindex SSE frames. Kept out of the components so the
 * three pieces that are easy to get wrong offline (multipart field names, the
 * SSE payload shapes, the file-type mapping) are unit-tested.
 */

export type FileKind =
  | "pdf"
  | "word"
  | "sheet"
  | "slide"
  | "image"
  | "archive"
  | "url"
  | "text"
  | "code"
  | "other";

const KIND_BY_EXTENSION: Record<string, FileKind> = {
  pdf: "pdf",
  doc: "word",
  docx: "word",
  odt: "word",
  rtf: "word",
  xls: "sheet",
  xlsx: "sheet",
  csv: "sheet",
  ods: "sheet",
  ppt: "slide",
  pptx: "slide",
  odp: "slide",
  png: "image",
  jpg: "image",
  jpeg: "image",
  gif: "image",
  webp: "image",
  bmp: "image",
  tif: "image",
  tiff: "image",
  svg: "image",
  zip: "archive",
  rar: "archive",
  "7z": "archive",
  tar: "archive",
  gz: "archive",
  txt: "text",
  md: "text",
  html: "text",
  mhtml: "text",
  py: "code",
  js: "code",
  ts: "code",
  tsx: "code",
  json: "code",
  yaml: "code",
  yml: "code",
  xml: "code",
  sql: "code",
  java: "code",
  c: "code",
  cpp: "code",
  go: "code",
  rs: "code",
  sh: "code",
};

/**
 * The visual kind of a row. Takes the API's ``type`` (the extension or ``url``)
 * and falls back to the name's suffix for rows written before ``type`` existed.
 */
export function fileKind(typeOrName: string | null | undefined): FileKind {
  const raw = (typeOrName ?? "").trim().toLowerCase();
  if (!raw) return "other";
  if (raw === "url" || raw.startsWith("http://") || raw.startsWith("https://")) {
    return "url";
  }
  const extension = raw.includes(".") ? raw.slice(raw.lastIndexOf(".") + 1) : raw;
  return KIND_BY_EXTENSION[extension] ?? "other";
}

/** ``6983734`` 鈫?``6,983,734``; the backend sends ``"-"`` for unknown values. */
export function formatTokens(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toLocaleString("en-US") : "-";
  }
  const text = value.trim();
  if (text === "" || text === "-") return "-";
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed.toLocaleString("en-US") : text;
}

/** ``true`` when the loader cell carries the backend's failure marker. */
export function isLoaderWarning(value: string | null | undefined): boolean {
  return (value ?? "").trimStart().startsWith("\u26a0");
}

/** Bytes of a picked file; the row's ``size`` column is already formatted. */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}

export interface UploadFormInput {
  files: File[];
  /** One URL per line; empty lines are dropped by the backend. */
  urls: string;
  indexId?: string | number;
  reindex: boolean;
}

/**
 * The multipart body of `POST /files/upload`.
 *
 * Field names and their multiplicity are part of the API contract: ``files`` is
 * repeated once per upload, ``urls`` is one newline-separated string, ``reindex``
 * is a form boolean. ``index_id`` is omitted rather than sent empty so the
 * backend falls back to its default index.
 */
export function buildUploadForm(input: UploadFormInput): FormData {
  const form = new FormData();
  for (const file of input.files) {
    form.append("files", file, file.name);
  }
  const urls = input.urls.trim();
  if (urls) form.append("urls", urls);
  if (input.indexId !== undefined && input.indexId !== null && input.indexId !== "") {
    form.append("index_id", String(input.indexId));
  }
  form.append("reindex", input.reindex ? "true" : "false");
  return form;
}

export type UploadEvent =
  | { type: "progress"; line: string }
  | { type: "done"; ids: string[]; errors: string[] }
  | { type: "error"; message: string };

function parseJson<T>(data: string): T | null {
  try {
    return JSON.parse(data) as T;
  } catch {
    return null;
  }
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

/** One SSE frame of the upload/reindex stream, or ``null`` for an unknown one. */
export function parseUploadEvent(event: SseEvent): UploadEvent | null {
  if (event.event === "progress") {
    const payload = parseJson<{ line?: unknown }>(event.data);
    if (!payload || typeof payload.line !== "string") return null;
    return { type: "progress", line: payload.line };
  }
  if (event.event === "done") {
    const payload = parseJson<{ ids?: unknown; errors?: unknown }>(event.data);
    if (!payload) return null;
    return { type: "done", ids: stringList(payload.ids), errors: stringList(payload.errors) };
  }
  if (event.event === "error") {
    const payload = parseJson<{ message?: unknown }>(event.data);
    const message =
      payload && typeof payload.message === "string" ? payload.message : event.data;
    return { type: "error", message };
  }
  return null;
}
