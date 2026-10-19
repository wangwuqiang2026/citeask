import { Blocks, CircleAlert, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useFileChunks } from "@/components/files/hooks";
import { useT, type MessageKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const TYPE_KEYS: Record<string, MessageKey> = {
  text: "fileChunks.type.text",
  table: "fileChunks.type.table",
  image: "fileChunks.type.image",
  thumbnail: "fileChunks.type.thumbnail",
};

const TYPE_ORDER = ["text", "table", "image", "thumbnail"] as const;

interface ChunksDrawerProps {
  fileId: string;
  fileName: string;
  onClose: () => void;
}

/**
 * Slide-over with the parsed chunks of one file. Mirrors the chat page's
 * evidence drawer: backdrop button, Escape to close, focus on the close control.
 */
export function ChunksDrawer({ fileId, fileName, onClose }: ChunksDrawerProps) {
  const t = useT();
  const [type, setType] = useState("all");
  const closeRef = useRef<HTMLButtonElement>(null);
  const { data, isLoading, isError, refetch, isFetching } = useFileChunks(fileId, type);

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const counts = useMemo(() => data?.counts ?? {}, [data?.counts]);
  const total = useMemo(
    () => TYPE_ORDER.reduce((sum, kind) => sum + (counts[kind] ?? 0), 0),
    [counts],
  );
  const filters = useMemo(() => {
    const present = TYPE_ORDER.filter((kind) => (counts[kind] ?? 0) > 0);
    return ["all", ...present];
  }, [counts]);

  const typeLabel = (kind: string): string => {
    const key = TYPE_KEYS[kind];
    return key ? t(key) : t("fileChunks.type.other");
  };

  return (
    <div
      className="fixed inset-0 z-40"
      role="dialog"
      aria-modal="true"
      aria-label={t("fileChunks.title")}
    >
      <button
        type="button"
        aria-label={t("common.close")}
        className="absolute inset-0 bg-black/35"
        onClick={onClose}
      />
      <div className="absolute inset-y-0 right-0 flex w-[min(560px,94vw)] flex-col border-l border-border bg-panel shadow-pop">
        <header className="flex items-center gap-2 border-b border-border px-4 py-3">
          <Blocks className="h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-sm font-semibold text-fg" title={fileName}>
              {fileName}
            </h2>
            <p className="text-2xs text-subtle">
              {t("fileChunks.counts", { n: total })}
            </p>
          </div>
          <Button
            ref={closeRef}
            variant="ghost"
            size="icon-sm"
            aria-label={t("fileChunks.close")}
            onClick={onClose}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </header>

        <div className="flex flex-wrap items-center gap-1.5 border-b border-border px-4 py-2">
          {filters.map((kind) => {
            const active = type === kind;
            const label = kind === "all" ? t("fileChunks.all") : typeLabel(kind);
            const count = kind === "all" ? total : (counts[kind] ?? 0);
            return (
              <button
                key={kind}
                type="button"
                aria-pressed={active}
                onClick={() => setType(kind)}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-2xs transition-colors",
                  active
                    ? "border-accent/40 bg-accent/10 text-accent"
                    : "border-border text-muted hover:bg-elevated hover:text-fg",
                )}
              >
                {label}
                <span className="font-mono tabular-nums opacity-70">{count}</span>
              </button>
            );
          })}
          {isFetching ? (
            <span className="ml-auto text-2xs text-subtle" role="status">
              {t("common.loading")}
            </span>
          ) : null}
        </div>

        <div className="scroll-thin min-h-0 flex-1 overflow-y-auto p-3">
          {isLoading && !data ? (
            <div className="space-y-2">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-2/3" />
            </div>
          ) : isError ? (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
            >
              <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p>{t("fileChunks.loadError")}</p>
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-2"
                  onClick={() => void refetch()}
                >
                  {t("common.retry")}
                </Button>
              </div>
            </div>
          ) : (data?.chunks.length ?? 0) === 0 ? (
            <div className="rounded-md border border-dashed border-border bg-elevated p-6 text-center text-sm text-muted">
              {t("fileChunks.empty")}
            </div>
          ) : (
            <ul className="space-y-2">
              {data?.chunks.map((chunk) => (
                <li key={chunk.index}>
                  <article className="rounded-md border border-border bg-panel p-3">
                    <header className="mb-2 flex flex-wrap items-center gap-1.5">
                      <span className="font-mono text-2xs text-subtle">
                        #{chunk.index}
                      </span>
                      {chunk.page !== null ? (
                        <Badge variant="outline">
                          {t("fileChunks.page", { n: chunk.page })}
                        </Badge>
                      ) : null}
                      <Badge variant="subtle">{typeLabel(chunk.type)}</Badge>
                    </header>
                    <p
                      className={cn(
                        "whitespace-pre-wrap break-words text-sm leading-relaxed",
                        chunk.type === "table"
                          ? "font-mono text-xs text-fg"
                          : "text-muted",
                      )}
                    >
                      {chunk.text}
                    </p>
                  </article>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
