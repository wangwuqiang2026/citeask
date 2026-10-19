import {
  Blocks,
  Download,
  MoreHorizontal,
  RefreshCw,
  Trash2,
} from "lucide-react";
import type { MouseEvent } from "react";

import { FileTypeIcon } from "@/components/files/file-icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { formatTokens, isLoaderWarning } from "@/lib/files";
import { useT, type MessageKey } from "@/lib/i18n";
import type { FileRow } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ColumnSpec {
  labelKey: MessageKey;
  /** Width/visibility classes; `name` stays auto so it absorbs the remainder. */
  className: string;
}

/**
 * How each API column is rendered. `file_id` never reaches the table (it is an
 * internal handle), and the layout keeps only the essential columns visible on
 * narrow screens — the table never overflows at 1280 / 1024 / 820.
 */
const COLUMNS: Record<string, ColumnSpec> = {
  name: { labelKey: "files.col.name", className: "" },
  type: { labelKey: "files.col.type", className: "w-16" },
  size: { labelKey: "files.col.size", className: "hidden w-24 md:table-cell" },
  blocks: { labelKey: "files.col.blocks", className: "hidden w-20 sm:table-cell" },
  loader: { labelKey: "files.col.loader", className: "hidden w-32 lg:table-cell" },
  profile: { labelKey: "files.col.profile", className: "hidden w-52 xl:table-cell" },
  date_created: {
    labelKey: "files.col.created",
    className: "hidden w-36 lg:table-cell",
  },
  tokens: { labelKey: "files.col.tokens", className: "hidden w-24 xl:table-cell" },
};

function specFor(column: string): ColumnSpec {
  return (
    COLUMNS[column] ?? {
      labelKey: "files.col.tokens",
      className: "hidden w-32 xl:table-cell",
    }
  );
}

interface FileTableProps {
  rows: FileRow[];
  columns: string[];
  selectedId: string | null;
  busyId?: string | null;
  onSelect: (fileId: string) => void;
  onOpenChunks: (row: FileRow) => void;
  onDownload: (row: FileRow) => void;
  onReindex: (row: FileRow) => void;
  onDelete: (row: FileRow) => void;
}

function Cell({ column, row }: { column: string; row: FileRow }) {
  switch (column) {
    case "name":
      return (
        <span className="flex min-w-0 items-center gap-2">
          <FileTypeIcon type={row.type || row.name} />
          <span className="truncate text-sm text-fg" title={row.name}>
            {row.name}
          </span>
        </span>
      );
    case "type":
      return (
        <Badge variant="outline" className="font-mono uppercase">
          {row.type || "-"}
        </Badge>
      );
    case "size":
      return <span className="font-mono text-2xs text-muted">{row.size || "-"}</span>;
    case "blocks":
      return (
        <span className="font-mono text-2xs tabular-nums text-muted">
          {Number.isFinite(row.blocks) ? row.blocks : 0}
        </span>
      );
    case "loader":
      return (
        <span
          className={cn(
            "block truncate text-xs",
            isLoaderWarning(row.loader) ? "text-danger" : "text-muted",
          )}
          title={row.loader}
        >
          {row.loader || "-"}
        </span>
      );
    case "profile":
      return (
        <span className="block truncate text-xs text-subtle" title={row.profile}>
          {row.profile || "-"}
        </span>
      );
    case "date_created":
      return (
        <span className="font-mono text-2xs text-subtle">
          {row.date_created || "-"}
        </span>
      );
    case "tokens":
      return (
        <span className="font-mono text-2xs tabular-nums text-muted">
          {formatTokens(row.tokens)}
        </span>
      );
    default: {
      const value = (row as unknown as Record<string, unknown>)[column];
      return (
        <span className="block truncate text-xs text-muted">{String(value ?? "-")}</span>
      );
    }
  }
}

/** The file table. The page owns loading/empty/error states around it. */
export function FileTable({
  rows,
  columns,
  selectedId,
  busyId,
  onSelect,
  onOpenChunks,
  onDownload,
  onReindex,
  onDelete,
}: FileTableProps) {
  const t = useT();
  const visible = columns.filter((column) => column !== "file_id");

  const stop = (event: MouseEvent) => event.stopPropagation();

  return (
    <div className="overflow-hidden rounded-md border border-border bg-panel">
      <table className="w-full table-fixed border-collapse text-left">
        <caption className="sr-only">{t("files.title")}</caption>
        <thead className="sticky top-0 z-10 bg-panel">
          <tr className="border-b border-border">
            {visible.map((column) => (
              <th
                key={column}
                scope="col"
                className={cn(
                  "bg-panel px-3 py-2 text-2xs font-medium uppercase tracking-wide text-subtle",
                  specFor(column).className,
                )}
              >
                {t(specFor(column).labelKey)}
              </th>
            ))}
            <th scope="col" className="w-14 bg-panel px-2 py-2">
              <span className="sr-only">{t("files.actions")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const selected = row.file_id === selectedId;
            const busy = row.file_id === busyId;
            return (
              <tr
                key={row.file_id}
                onClick={() => onSelect(row.file_id)}
                aria-current={selected ? "true" : undefined}
                className={cn(
                  "group border-b border-border transition-colors last:border-b-0",
                  "cursor-pointer hover:bg-elevated",
                  selected && "bg-accent/[0.06] hover:bg-accent/[0.09]",
                )}
              >
                {visible.map((column) => (
                  <td
                    key={column}
                    className={cn(
                      "px-3 py-2 align-middle",
                      specFor(column).className,
                    )}
                  >
                    <Cell column={column} row={row} />
                  </td>
                ))}
                <td className="px-2 py-2" onClick={stop}>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`${t("files.actions")} · ${row.name}`}
                        disabled={busy}
                      >
                        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onSelect={() => onOpenChunks(row)}>
                        <Blocks className="h-4 w-4" aria-hidden="true" />
                        {t("files.viewChunks")}
                      </DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => onDownload(row)}>
                        <Download className="h-4 w-4" aria-hidden="true" />
                        {t("files.download")}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onSelect={() => onReindex(row)}
                        disabled={busy}
                      >
                        <RefreshCw
                          className={cn("h-4 w-4", busy && "animate-spin")}
                          aria-hidden="true"
                        />
                        {t("files.reindexAction")}
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onSelect={() => onDelete(row)}
                        className="text-danger focus:text-danger"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                        {t("files.delete")}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Reserved-space placeholder so the table does not jump when data arrives. */
export function FileTableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div
      className="overflow-hidden rounded-md border border-border bg-panel"
      aria-busy="true"
    >
      <div className="flex items-center gap-3 border-b border-border px-3 py-2.5">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-3 w-12" />
        <Skeleton className="ml-auto h-3 w-16" />
      </div>
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="flex items-center gap-3 border-b border-border px-3 py-3 last:border-b-0"
        >
          <Skeleton className="h-4 w-4 rounded-sm" />
          <Skeleton className="h-3.5 flex-1" />
          <Skeleton className="hidden h-3.5 w-14 sm:block" />
          <Skeleton className="hidden h-3.5 w-16 md:block" />
        </div>
      ))}
    </div>
  );
}
