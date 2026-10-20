import { CircleAlert, FolderOpen, RefreshCw, Search, Upload } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { PageFrame } from "@/components/app/PageFrame";
import { ChunksDrawer } from "@/components/files/ChunksDrawer";
import { ConfirmDialog } from "@/components/files/ConfirmDialog";
import {
  FileTable,
  FileTableSkeleton,
} from "@/components/files/FileTable";
import { GroupsPanel } from "@/components/files/GroupsPanel";
import { UploadDialog } from "@/components/files/UploadDialog";
import {
  useDebouncedValue,
  useDeleteFile,
  useFiles,
  useGroups,
} from "@/components/files/hooks";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { FileRow } from "@/lib/types";
import { useMeta } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

const DEFAULT_COLUMNS = [
  "file_id",
  "name",
  "type",
  "size",
  "blocks",
  "loader",
  "profile",
  "date_created",
  "tokens",
];

type Tab = "files" | "groups";

/**
 * `/files`: search, upload, the file table with per-row actions, the chunk
 * drawer and the group manager. Advanced indexing options still live in the
 * classic UI; the hint at the bottom says so instead of pretending otherwise.
 */
export function FilesPage() {
  const t = useT();
  const meta = useMeta();
  const index = meta.data?.indices?.[0];
  const indexId = index?.id;
  const indexName = index?.name;

  const [tab, setTab] = useState<Tab>("files");
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query);
  const files = useFiles(indexId, debouncedQuery);
  const groups = useGroups(indexId);

  const deleteFile = useDeleteFile(indexId);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [chunksTarget, setChunksTarget] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<FileRow | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  const rows = files.data?.rows ?? [];
  const columns = files.data?.columns ?? DEFAULT_COLUMNS;
  const groupCount = groups.data?.items.length ?? 0;

  const onDownload = (row: FileRow) => {
    // `noopener` forces a null return by spec, so the result says nothing about
    // success; the download endpoint is best-effort and errors show up in the UI
    // only when the request itself fails.
    void window.open(api.downloadFileUrl(row.file_id), "_blank", "noopener");
  };

  const onReindex = async (row: FileRow) => {
    setBusyId(row.file_id);
    try {
      await api.reindexFile(row.file_id, {
        onDone: ({ errors }) => {
          if (errors.length) {
            toast.warning(t("files.uploadPartial", { n: errors.length }));
          } else {
            toast.success(t("files.reindexDone", { name: row.name }));
          }
        },
        onError: ({ message }) => toast.error(message || t("files.reindexFailed")),
      });
      await files.refetch();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("files.reindexFailed"));
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteFile.mutateAsync(deleteTarget.file_id);
      toast.success(t("files.deleted", { name: deleteTarget.name }));
      if (selectedId === deleteTarget.file_id) setSelectedId(null);
      setDeleteTarget(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("files.deleteFailed"));
    }
  };

  const retry = () => {
    void files.refetch();
  };

  const headerActions = (
    <>
      <div className="relative">
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-subtle"
          aria-hidden="true"
        />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("files.searchPlaceholder")}
          aria-label={t("files.searchPlaceholder")}
          className="h-8 w-40 pl-7 text-sm sm:w-56"
        />
      </div>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={t("files.refresh")}
        onClick={retry}
        disabled={files.isFetching}
      >
        <RefreshCw
          className={cn("h-4 w-4", files.isFetching && "animate-spin")}
          aria-hidden="true"
        />
      </Button>
      <Button
        variant="primary"
        size="sm"
        onClick={() => setUploadOpen(true)}
        disabled={index === undefined}
      >
        <Upload className="h-4 w-4" aria-hidden="true" />
        <span className="hidden sm:inline">{t("files.upload")}</span>
      </Button>
    </>
  );

  // The default index is named after the page itself ("文件集合"), so showing
  // both reads like a duplicated title; only keep the names that add information.
  const subtitle = [
    indexName && indexName !== t("files.title") ? indexName : null,
    files.data ? t("files.count", { n: rows.length }) : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <>
      <PageFrame
        wide
        title={t("files.title")}
        subtitle={subtitle || t("files.subtitle")}
        actions={headerActions}
        footer={
          <div className="flex items-center gap-2 border-t border-border bg-panel px-5 py-2 text-2xs text-subtle">
            <span className="truncate">{t("files.classicHint")}</span>
            <a
              href="/legacy"
              target="_blank"
              rel="noreferrer"
              className="shrink-0 text-accent hover:underline"
            >
              {t("classic.open")}
            </a>
          </div>
        }
      >
        <div
          role="tablist"
          aria-label={t("files.title")}
          className="mb-4 flex items-center gap-1 border-b border-border"
        >
          {(
            [
              ["files", t("files.tabFiles"), rows.length, files.isSuccess],
              ["groups", t("files.tabGroups"), groupCount, groups.isSuccess],
            ] as const
          ).map(([value, label, count, ready]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              onClick={() => setTab(value)}
              className={cn(
                "-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm transition-colors",
                tab === value
                  ? "border-accent text-fg"
                  : "border-transparent text-muted hover:text-fg",
              )}
            >
              {label}
              {ready ? (
                <span className="rounded-full bg-elevated px-1.5 text-2xs tabular-nums text-subtle">
                  {count}
                </span>
              ) : null}
            </button>
          ))}
        </div>

        {tab === "groups" ? (
          <GroupsPanel indexId={indexId} />
        ) : files.isLoading ? (
          <FileTableSkeleton />
        ) : files.isError ? (
          <div
            role="alert"
            className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger"
          >
            <CircleAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="flex-1">{t("files.loadError")}</span>
            <Button variant="secondary" size="sm" onClick={retry}>
              {t("common.retry")}
            </Button>
          </div>
        ) : index === undefined ? (
          <EmptyFiles
            icon={<FolderOpen className="h-5 w-5" aria-hidden="true" />}
            title={t("files.indexMissing")}
            body={t("files.classicHint")}
          />
        ) : rows.length === 0 && debouncedQuery.trim() ? (
          <EmptyFiles
            icon={<Search className="h-5 w-5" aria-hidden="true" />}
            title={t("files.noMatch")}
            body={t("files.searchPlaceholder")}
          />
        ) : rows.length === 0 ? (
          <EmptyFiles
            icon={<FolderOpen className="h-5 w-5" aria-hidden="true" />}
            title={t("files.emptyTitle")}
            body={t("files.emptyBody")}
            action={
              <Button variant="primary" size="sm" onClick={() => setUploadOpen(true)}>
                <Upload className="h-4 w-4" aria-hidden="true" />
                {t("files.upload")}
              </Button>
            }
          />
        ) : (
          <FileTable
            rows={rows}
            columns={columns}
            selectedId={selectedId}
            busyId={busyId}
            onSelect={setSelectedId}
            onOpenChunks={(row) =>
              setChunksTarget({ id: row.file_id, name: row.name })
            }
            onDownload={onDownload}
            onReindex={(row) => void onReindex(row)}
            onDelete={setDeleteTarget}
          />
        )}
      </PageFrame>

      <UploadDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        indexId={indexId}
        indexName={indexName}
      />

      {chunksTarget ? (
        <ChunksDrawer
          fileId={chunksTarget.id}
          fileName={chunksTarget.name}
          onClose={() => setChunksTarget(null)}
        />
      ) : null}

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title={t("files.deleteTitle")}
        description={t("files.deleteDescription", {
          name: deleteTarget?.name ?? "",
        })}
        confirmLabel={t("common.delete")}
        pending={deleteFile.isPending}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}

function EmptyFiles({
  icon,
  title,
  body,
  action,
}: {
  icon: ReactNode;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-md border border-dashed border-border bg-panel px-6 py-14 text-center">
      <span className="inline-flex h-10 w-10 items-center justify-center rounded-md bg-elevated text-muted">
        {icon}
      </span>
      <div className="space-y-1">
        <p className="text-sm font-medium text-fg">{title}</p>
        <p className="mx-auto max-w-sm text-sm text-muted">{body}</p>
      </div>
      {action}
    </div>
  );
}
