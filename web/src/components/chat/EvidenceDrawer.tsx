import { ExternalLink, FileText, Image, Search, Table2, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useT } from "@/lib/i18n";
import type { EvidenceItem } from "@/lib/types";
import {
  cn,
  isRelevantEvidence,
  legacyFileUrl,
  relevancePercent,
} from "@/lib/utils";

interface EvidenceDrawerProps {
  items: EvidenceItem[];
  activeIndex: number | null;
  onClose?: () => void;
}

function typeLabel(key: string, t: ReturnType<typeof useT>): string {
  switch (key) {
    case "table":
      return t("evidence.type.table");
    case "image":
      return t("evidence.type.image");
    case "thumbnail":
      return t("evidence.type.thumbnail");
    case "text":
      return t("evidence.type.text");
    default:
      return t("evidence.type.other");
  }
}

function TypeIcon({ type }: { type: string | null | undefined }) {
  if (type === "table") return <Table2 className="h-4 w-4" aria-hidden="true" />;
  if (type === "image" || type === "thumbnail")
    return <Image className="h-4 w-4" aria-hidden="true" />;
  return <FileText className="h-4 w-4" aria-hidden="true" />;
}

function Highlighted({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <>{text}</>;
  const pattern = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
  const parts = text.split(pattern);
  return (
    <>
      {parts.map((part, index) =>
        pattern.test(part) ? (
          <mark key={index} className="rounded bg-accent/20 px-0.5 text-fg">
            {part}
          </mark>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  );
}

export function EvidenceDrawer({ items, activeIndex, onClose }: EvidenceDrawerProps) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [showAll, setShowAll] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  // The panel's job is to show the sources of this answer, not every chunk the
  // retrieval happened to keep: cited chunks and entity-row hits by default, the
  // rest behind "show all" (MODIFICATIONS §5.32). A turn with nothing relevant
  // (refusal, citations off) falls back to the candidates so the panel still
  // explains what was retrieved.
  const related = useMemo(() => items.filter(isRelevantEvidence), [items]);
  const showingAll = showAll || related.length === 0;

  const visible = useMemo(() => {
    const base = showingAll ? items : related;
    if (activeIndex === null) return base;
    const activeItem = items[activeIndex];
    // Keep the cited chunk the user just clicked visible even when filtered out.
    if (!activeItem || base.includes(activeItem)) return base;
    return [activeItem, ...base];
  }, [activeIndex, items, related, showingAll]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return visible;
    return visible.filter((item) =>
      `${item.file_name} ${item.text} ${item.type ?? ""}`.toLowerCase().includes(needle),
    );
  }, [visible, query]);

  useEffect(() => {
    if (activeIndex === null) return;
    const card = document.getElementById(`evidence-${activeIndex}`);
    card?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeIndex]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-panel">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2.5">
        <h2 className="text-sm font-semibold text-fg">{t("evidence.title")}</h2>
        <span className="text-2xs text-subtle">
          {showingAll
            ? t("evidence.count", { n: items.length })
            : t("evidence.countRelated", { n: related.length, total: items.length })}
        </span>
        <div className="flex-1" />
        {related.length > 0 && related.length < items.length ? (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-2xs"
            aria-pressed={showAll}
            onClick={() => setShowAll((current) => !current)}
          >
            {showAll
              ? t("evidence.showRelevant", { n: related.length })
              : t("evidence.showAll", { n: items.length })}
          </Button>
        ) : null}
        {onClose ? (
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t("evidence.close")}
            onClick={onClose}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        ) : null}
      </div>

      <div className="border-b border-border px-3 py-2">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-subtle"
            aria-hidden="true"
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("evidence.search")}
            aria-label={t("evidence.search")}
            className="h-8 pl-8 text-sm"
          />
        </div>
      </div>

      {items.length > 0 && related.length === 0 ? (
        <p className="border-b border-border bg-elevated px-3 py-2 text-2xs text-subtle">
          {t("evidence.relatedFallback")}
        </p>
      ) : null}

      <div ref={listRef} className="scroll-thin min-h-0 flex-1 overflow-y-auto p-3">
        {items.length === 0 ? (
          <div className="rounded-md border border-dashed border-border bg-elevated p-6 text-center text-sm text-muted">
            {t("evidence.empty")}
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-6 text-center text-sm text-muted">{t("evidence.noMatch")}</div>
        ) : (
          <ul className="space-y-2">
            {filtered.map((item) => {
              const originalIndex = items.indexOf(item);
              const active = activeIndex === originalIndex;
              const score = relevancePercent(item);
              // The percent is a *candidate ordering* hint from the local lexical
              // reranker, not semantic relevance. It only belongs next to the
              // candidate list, and a 0 is spelled out instead of shown as "0%",
              // which used to sit next to 已被引用 and looked like a bug (§5.32).
              const showScore = showingAll && !item.entity_row;
              return (
                <li key={item.id}>
                  <article
                    id={`evidence-${originalIndex}`}
                    aria-current={active ? "true" : undefined}
                    className={cn(
                      "rounded-md border p-3 transition-colors",
                      active
                        ? "border-accent/50 bg-accent/[0.06] ring-1 ring-accent/25"
                        : "border-border bg-panel hover:bg-elevated",
                    )}
                  >
                    <header className="flex items-start gap-2">
                      <span className="mt-0.5 text-muted">
                        <TypeIcon type={item.type} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p
                          className="truncate text-sm font-medium text-fg"
                          title={item.file_name}
                        >
                          {item.file_name}
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-1.5">
                          {item.page ? (
                            <Badge variant="outline">
                              {t("evidence.page", { n: item.page })}
                            </Badge>
                          ) : null}
                          <Badge variant="subtle">{typeLabel(item.type ?? "", t)}</Badge>
                          <Badge variant={item.cited ? "accent" : "outline"}>
                            {item.cited ? t("evidence.cited") : t("evidence.notCited")}
                          </Badge>
                          {item.entity_row ? (
                            <Badge variant="subtle">{t("evidence.entityRow")}</Badge>
                          ) : null}
                        </div>
                      </div>
                    </header>

                    {showScore ? (
                      <div className="mt-2.5 flex items-center gap-2">
                        <span className="shrink-0 text-2xs text-subtle">
                          {score > 0
                            ? t("evidence.literalMatch", { n: score })
                            : t("evidence.noLiteralMatch")}
                        </span>
                        {score > 0 ? (
                          <div
                            className="h-1.5 flex-1 overflow-hidden rounded-full bg-border"
                            role="img"
                            aria-label={t("evidence.literalMatch", { n: score })}
                          >
                            <div
                              className="h-full rounded-full bg-accent"
                              style={{ width: `${score}%` }}
                            />
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    <p className="mt-2 line-clamp-4 text-sm leading-relaxed text-muted">
                      <Highlighted text={item.text} query={query} />
                    </p>

                    <div className="mt-2 flex justify-end">
                      <a
                        href={legacyFileUrl(item.file_path, item.page)}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                      >
                        {t("evidence.open")}
                        <ExternalLink className="h-3 w-3" aria-hidden="true" />
                      </a>
                    </div>

                    <span className="sr-only">
                      {t("evidence.source")} {originalIndex + 1}
                    </span>
                  </article>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
