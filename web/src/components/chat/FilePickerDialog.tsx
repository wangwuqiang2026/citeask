import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type FileOption } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface FilePickerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (files: FileOption[]) => void;
  indexId?: string | number;
}

/**
 * Picks knowledge-base files. An unavailable endpoint (M2 before it ships, or a
 * permissions error surfaced as `null`) is a normal state: the dialog then
 * points at the classic UI instead of showing an error.
 */
export function FilePickerDialog({
  open,
  onOpenChange,
  onConfirm,
  indexId,
}: FilePickerDialogProps) {
  const t = useT();
  const [selected, setSelected] = useState<Record<string, FileOption>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["files", "picker", indexId ?? "all"],
    queryFn: () => api.tryListFiles(indexId),
    enabled: open,
    retry: false,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!open) setSelected({});
  }, [open]);

  const files = data ?? [];
  const chosen = Object.values(selected);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("chat.chooseFiles")}</DialogTitle>
          <DialogDescription>{t("chat.scope")}</DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-2/3" />
          </div>
        ) : data === null ? (
          <div className="rounded-md border border-border bg-elevated p-4 text-sm text-muted">
            <p>{t("chat.uploadSoon")}</p>
            <Button asChild variant="secondary" className="mt-3">
              <a href="/legacy" target="_blank" rel="noreferrer">
                {t("classic.open")}
              </a>
            </Button>
          </div>
        ) : files.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">{t("chat.emptyBody")}</p>
        ) : (
          <ul className="max-h-72 space-y-1 overflow-y-auto">
            {files.map((file) => {
              const checked = Boolean(selected[file.id]);
              return (
                <li key={file.id}>
                  <button
                    type="button"
                    aria-pressed={checked}
                    onClick={() =>
                      setSelected((current) => {
                        const next = { ...current };
                        if (next[file.id]) delete next[file.id];
                        else next[file.id] = file;
                        return next;
                      })
                    }
                    className={cn(
                      "flex w-full items-center gap-2 rounded-sm border px-3 py-2 text-left text-sm transition-colors",
                      checked
                        ? "border-accent/40 bg-accent/10 text-fg"
                        : "border-border bg-panel text-fg hover:bg-elevated",
                    )}
                  >
                    <FileText className="h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
                    <span className="min-w-0 flex-1 truncate">{file.file_name}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t("settings.done")}
          </Button>
          <Button
            variant="primary"
            disabled={chosen.length === 0}
            onClick={() => {
              onConfirm(chosen);
              onOpenChange(false);
            }}
          >
            {t("chat.chooseFiles")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
