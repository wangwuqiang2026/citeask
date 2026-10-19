import {
  CheckCircle2,
  CircleAlert,
  ExternalLink,
  FileText,
  UploadCloud,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api, ApiError } from "@/lib/api";
import { buildUploadForm, formatBytes } from "@/lib/files";
import { useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query";
import { cn } from "@/lib/utils";

type Phase = "idle" | "running" | "done" | "error";

interface UploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  indexId?: string | number;
  indexName?: string;
}

/**
 * Upload and index: drag-and-drop or pick files, optionally paste URLs, then
 * watch the SSE progress lines. The endpoint is the only file route with a
 * multipart body, so the form is assembled by `buildUploadForm` (unit-tested).
 */
export function UploadDialog({
  open,
  onOpenChange,
  indexId,
  indexName,
}: UploadDialogProps) {
  const t = useT();
  const queryClient = useQueryClient();

  const [files, setFiles] = useState<File[]>([]);
  const [urls, setUrls] = useState("");
  const [reindex, setReindex] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [lines, setLines] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<{ ids: number; errors: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const openRef = useRef(open);
  openRef.current = open;

  useEffect(() => {
    if (open) {
      setFiles([]);
      setUrls("");
      setReindex(false);
      setPhase("idle");
      setLines([]);
      setError(null);
      setSummary(null);
      setDragging(false);
    } else {
      controllerRef.current?.abort();
    }
  }, [open]);

  useEffect(() => {
    const node = logRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [lines.length]);

  const addFiles = (incoming: FileList | File[]) => {
    const next = Array.from(incoming);
    if (next.length === 0) return;
    setFiles((current) => [...current, ...next]);
  };

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["files", String(indexId ?? "all")] });
    void queryClient.invalidateQueries({ queryKey: queryKeys.groups(indexId) });
  };

  const submit = async () => {
    if (phase === "running") return;
    if (files.length === 0 && urls.trim() === "") {
      setError(t("files.noSelection"));
      return;
    }

    const controller = new AbortController();
    controllerRef.current = controller;
    setPhase("running");
    setLines([]);
    setError(null);
    setSummary(null);

    let finished = false;
    let failed = false;

    try {
      await api.uploadFiles(
        buildUploadForm({ files, urls, indexId, reindex }),
        {
          onProgress: ({ line }) => {
            if (openRef.current) setLines((current) => [...current, line]);
          },
          onDone: ({ ids, errors }) => {
            finished = true;
            if (!openRef.current) return;
            setPhase("done");
            setSummary({ ids: ids.length, errors: errors.length });
            invalidate();
            if (errors.length > 0) {
              toast.warning(t("files.uploadPartial", { n: errors.length }));
            } else {
              toast.success(t("files.uploadDone", { n: ids.length }));
            }
          },
          onError: ({ message }) => {
            failed = true;
            if (!openRef.current) return;
            setPhase("error");
            setError(message);
            invalidate();
          },
        },
        controller.signal,
      );

      if (!finished && !failed && openRef.current) {
        setPhase("done");
        invalidate();
      }
    } catch (caught) {
      if (controller.signal.aborted) {
        if (openRef.current) {
          setPhase("idle");
          setLines((current) => [...current, t("files.uploadCancelled")]);
        }
        return;
      }
      if (!openRef.current) return;
      setPhase("error");
      setError(
        caught instanceof ApiError || caught instanceof Error
          ? caught.message
          : t("error.generic"),
      );
      invalidate();
    }
  };

  const running = phase === "running";

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) controllerRef.current?.abort();
        onOpenChange(next);
      }}
    >
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{t("files.uploadTitle")}</DialogTitle>
          <DialogDescription>
            {indexName
              ? `${indexName} · ${t("files.uploadDescription")}`
              : t("files.uploadDescription")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div
            onDragOver={(event) => {
              event.preventDefault();
              if (!running) setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              if (!running) addFiles(event.dataTransfer.files);
            }}
            className={cn(
              "flex flex-col items-center justify-center gap-2 rounded-md border border-dashed px-4 py-6 text-center transition-colors",
              dragging
                ? "border-accent bg-accent/[0.06]"
                : "border-border bg-elevated/40",
            )}
          >
            <UploadCloud
              className={cn("h-6 w-6", dragging ? "text-accent" : "text-subtle")}
              aria-hidden="true"
            />
            <p className="text-sm text-fg">{t("files.dropTitle")}</p>
            <p className="text-xs text-subtle">{t("files.dropBody")}</p>
            <input
              ref={inputRef}
              type="file"
              multiple
              className="sr-only"
              aria-label={t("a11y.uploadFiles")}
              onChange={(event) => {
                if (event.target.files) addFiles(event.target.files);
                event.target.value = "";
              }}
            />
            <Button
              variant="secondary"
              size="sm"
              className="mt-1"
              disabled={running}
              onClick={() => inputRef.current?.click()}
            >
              {t("files.choose")}
            </Button>
          </div>

          {files.length > 0 ? (
            <ul className="max-h-40 space-y-1 overflow-y-auto" aria-live="polite">
              {files.map((file, index) => (
                <li
                  key={`${file.name}-${index}`}
                  className="flex items-center gap-2 rounded-sm border border-border px-2.5 py-1.5"
                >
                  <FileText className="h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate text-sm text-fg">
                    {file.name}
                  </span>
                  <span className="shrink-0 font-mono text-2xs text-subtle">
                    {formatBytes(file.size)}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`${t("files.removeFile")} · ${file.name}`}
                    disabled={running}
                    onClick={() =>
                      setFiles((current) => current.filter((_, i) => i !== index))
                    }
                  >
                    <X className="h-3.5 w-3.5" aria-hidden="true" />
                  </Button>
                </li>
              ))}
            </ul>
          ) : null}

          <div>
            <label
              htmlFor="files-upload-urls"
              className="mb-1 block text-sm font-medium text-fg"
            >
              {t("files.urlsLabel")}
            </label>
            <Textarea
              id="files-upload-urls"
              rows={3}
              value={urls}
              disabled={running}
              onChange={(event) => setUrls(event.target.value)}
              placeholder={t("files.urlsPlaceholder")}
              className="text-sm"
            />
          </div>

          <div className="flex items-center justify-between gap-4">
            <label htmlFor="files-upload-reindex" className="text-sm text-fg">
              {t("files.reindex")}
            </label>
            <Switch
              id="files-upload-reindex"
              checked={reindex}
              disabled={running}
              onCheckedChange={setReindex}
            />
          </div>

          {error ? (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-sm border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
            >
              <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="min-w-0 flex-1 break-words">{error}</span>
            </div>
          ) : null}

          {summary ? (
            <div
              role="status"
              className={cn(
                "flex items-start gap-2 rounded-sm border px-3 py-2 text-sm",
                summary.errors > 0
                  ? "border-danger/30 bg-danger/10 text-danger"
                  : "border-success/30 bg-success/10 text-success",
              )}
            >
              {summary.errors > 0 ? (
                <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              ) : (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              )}
              <span>
                {summary.errors > 0
                  ? t("files.uploadPartial", { n: summary.errors })
                  : t("files.uploadDone", { n: summary.ids })}
              </span>
            </div>
          ) : null}

          {lines.length > 0 || running ? (
            <section aria-live="polite">
              <p className="mb-1 text-2xs font-medium uppercase tracking-wide text-subtle">
                {t("files.progressTitle")}
              </p>
              <div
                ref={logRef}
                className="scroll-thin max-h-40 overflow-y-auto rounded-sm border border-border bg-elevated p-2 font-mono text-2xs leading-relaxed text-muted"
              >
                {lines.length === 0 ? (
                  <p className="text-subtle">{t("files.progressEmpty")}</p>
                ) : (
                  lines.map((line, index) => <p key={index}>{line}</p>)
                )}
              </div>
            </section>
          ) : null}
        </div>

        <div className="mt-4 flex items-center justify-between gap-2">
          <a
            href="/legacy"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-subtle hover:text-fg"
          >
            {t("files.classicHint")}
            <ExternalLink className="h-3 w-3" aria-hidden="true" />
          </a>
          <div className="flex items-center gap-2">
            {running ? (
              <Button variant="secondary" onClick={() => controllerRef.current?.abort()}>
                {t("files.cancelUpload")}
              </Button>
            ) : (
              <Button variant="ghost" onClick={() => onOpenChange(false)}>
                {t("files.close")}
              </Button>
            )}
            <Button
              variant="primary"
              onClick={() => void submit()}
              disabled={running || (files.length === 0 && urls.trim() === "")}
            >
              {running
                ? t("files.uploading")
                : phase === "error"
                  ? t("common.retry")
                  : t("files.start")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
