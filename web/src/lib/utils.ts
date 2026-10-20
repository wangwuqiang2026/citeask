import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { ConversationSummary } from "./types";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export type GroupLabelKey =
  | "date.today"
  | "date.yesterday"
  | "date.previous7"
  | "date.earlier";

export interface ConversationGroup {
  key: GroupLabelKey;
  items: ConversationSummary[];
}

const DAY = 24 * 60 * 60 * 1000;

/**
 * Group conversations the way chat products do: today, yesterday, previous 7
 * days, earlier. The server sends ISO timestamps; an unparsable date is treated
 * as "earlier" rather than dropping the row.
 */
export function groupConversations(
  items: ConversationSummary[],
  now: Date = new Date(),
): ConversationGroup[] {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfYesterday = startOfToday - DAY;
  const startOfWeek = startOfToday - 6 * DAY;

  const groups: Record<GroupLabelKey, ConversationSummary[]> = {
    "date.today": [],
    "date.yesterday": [],
    "date.previous7": [],
    "date.earlier": [],
  };

  for (const item of items) {
    const raw = item.date_updated || item.date_created;
    const time = new Date(raw).getTime();
    if (!Number.isFinite(time)) {
      groups["date.earlier"].push(item);
    } else if (time >= startOfToday) {
      groups["date.today"].push(item);
    } else if (time >= startOfYesterday) {
      groups["date.yesterday"].push(item);
    } else if (time >= startOfWeek) {
      groups["date.previous7"].push(item);
    } else {
      groups["date.earlier"].push(item);
    }
  }

  return (Object.keys(groups) as GroupLabelKey[])
    .filter((key) => groups[key].length > 0)
    .map((key) => ({ key, items: groups[key] }));
}

export function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function formatDateLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/** `/legacy/file=…` URL for a citation source. */
export function legacyFileUrl(filePath: string | null | undefined, page?: number | null): string {
  if (!filePath) return "/legacy";
  // The backend hands over a native path (absolute on Windows); the Gradio
  // `/file=` route expects it URL-encoded (backend contract note 4).
  const url = `/legacy/file=${encodeURIComponent(filePath)}`;
  return page && page > 0 ? `${url}#page=${page}` : url;
}

export function relevancePercent(item: {
  score?: number | null;
  rerank_score?: number | null;
  vector_score?: number | null;
}): number {
  const raw = item.rerank_score ?? item.score ?? item.vector_score ?? 0;
  if (!Number.isFinite(raw)) return 0;
  // Reranker scores are 0..1 (and occasionally 0..10); the bar is a hint, not a
  // measurement, so clamp instead of trying to rescale.
  return Math.max(0, Math.min(100, Math.round(raw * 100)));
}

/**
 * Whether the evidence panel lists this chunk as relevant (MODIFICATIONS §5.32).
 *
 * Two independent signals count: the answer cited the chunk, or the retrieval
 * promoted it because it names the queried entity in a table cell
 * (``entity_row``). Everything else is a retrieval *candidate* — shown under
 * "show all", but not by default. A chunk without a vector score
 * (``NO_SIMILARITY`` = -1.0) came from the entity-row or full-text pass; old
 * conversations stored before ``entity_row`` existed only have that signal, so
 * the flag's absence falls back to it. Once the payload carries the flag, trust
 * it: a full-text-only hit is not an entity row.
 */
export function isRelevantEvidence(item: {
  cited?: boolean;
  entity_row?: boolean;
  vector_score?: number | null;
}): boolean {
  if (item.cited) return true;
  if (item.entity_row === true) return true;
  if (item.entity_row === undefined) return item.vector_score === -1;
  return false;
}

export function clampText(text: string, max = 240): string {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max).trimEnd()}…` : clean;
}

/**
 * Whether a composer keydown sends the message.
 *
 * Enter sends unless Shift is held; Ctrl/Meta+Enter is an explicit shortcut and
 * keeps working with Shift, as the old inline handler did. While an IME is
 * composing, Enter picks a candidate — sending there would swallow the word
 * being typed. Chrome/Firefox set ``isComposing``; older WebKit only bumps
 * ``keyCode`` to the 229 sentinel.
 */
export function shouldSubmitOnEnter(event: {
  key: string;
  shiftKey?: boolean;
  ctrlKey?: boolean;
  metaKey?: boolean;
  isComposing?: boolean;
  keyCode?: number;
}): boolean {
  if (event.isComposing === true || event.keyCode === 229) return false;
  if (event.key !== "Enter") return false;
  return event.ctrlKey === true || event.metaKey === true || event.shiftKey !== true;
}
