import { CircleAlert, FolderPlus, Layers, Pencil, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/files/ConfirmDialog";
import { FileTypeIcon } from "@/components/files/file-icon";
import {
  useCreateGroup,
  useDeleteGroup,
  useFiles,
  useGroups,
  useUpdateGroup,
} from "@/components/files/hooks";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { FileGroupItem } from "@/lib/types";
import { cn } from "@/lib/utils";

interface GroupsPanelProps {
  indexId?: string | number;
}

type Editor =
  | { mode: "create" }
  | { mode: "edit"; group: FileGroupItem }
  | null;

/** File groups: list, create/edit (name + multi-select files) and delete. */
export function GroupsPanel({ indexId }: GroupsPanelProps) {
  const t = useT();
  const groups = useGroups(indexId);
  const files = useFiles(indexId, "");
  const createGroup = useCreateGroup(indexId);
  const updateGroup = useUpdateGroup(indexId);
  const deleteGroup = useDeleteGroup(indexId);

  const [editor, setEditor] = useState<Editor>(null);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [fileSearch, setFileSearch] = useState("");
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<FileGroupItem | null>(null);

  const rows = useMemo(() => files.data?.rows ?? [], [files.data?.rows]);
  const visibleFiles = useMemo(() => {
    const needle = fileSearch.trim().toLowerCase();
    return needle
      ? rows.filter((row) => row.name.toLowerCase().includes(needle))
      : rows;
  }, [rows, fileSearch]);

  const openCreate = () => {
    setEditor({ mode: "create" });
    setName("");
    setSelected([]);
    setFileSearch("");
    setDialogError(null);
  };

  const openEdit = (group: FileGroupItem) => {
    setEditor({ mode: "edit", group });
    setName(group.name);
    setSelected(group.files);
    setFileSearch("");
    setDialogError(null);
  };

  const toggleFile = (fileId: string) => {
    setSelected((current) =>
      current.includes(fileId)
        ? current.filter((id) => id !== fileId)
        : [...current, fileId],
    );
  };

  const save = async () => {
    if (!editor) return;
    const trimmed = name.trim();
    if (!trimmed) {
      setDialogError(t("groups.nameRequired"));
      return;
    }
    try {
      if (editor.mode === "edit") {
        await updateGroup.mutateAsync({
          id: editor.group.id,
          name: trimmed,
          files: selected,
        });
        toast.success(t("groups.updated"));
      } else {
        await createGroup.mutateAsync({ name: trimmed, files: selected });
        toast.success(t("groups.created"));
      }
      setEditor(null);
    } catch (error) {
      setDialogError(
        error instanceof ApiError ? error.message : t("error.generic"),
      );
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteGroup.mutateAsync(deleteTarget.id);
      toast.success(t("groups.deleted"));
      setDeleteTarget(null);
    } catch {
      toast.error(t("error.generic"));
    }
  };

  const groupCount = groups.data?.items.length ?? 0;
  const saving = createGroup.isPending || updateGroup.isPending;

  return (
    <section className="overflow-hidden rounded-md border border-border bg-panel">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Layers className="h-4 w-4 text-muted" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-fg">{t("groups.title")}</h2>
        <span className="text-2xs text-subtle">
          {t("groups.count", { n: groupCount })}
        </span>
        <div className="ml-auto">
          <Button variant="primary" size="sm" onClick={openCreate}>
            <FolderPlus className="h-4 w-4" aria-hidden="true" />
            {t("groups.create")}
          </Button>
        </div>
      </div>

      {groups.isLoading ? (
        <div className="space-y-px p-4" aria-busy="true">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-2/3" />
        </div>
      ) : groups.isError ? (
        <div
          role="alert"
          className="m-4 flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        >
          <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p>{t("groups.loadError")}</p>
            <Button
              variant="secondary"
              size="sm"
              className="mt-2"
              onClick={() => void groups.refetch()}
            >
              {t("common.retry")}
            </Button>
          </div>
        </div>
      ) : groupCount === 0 ? (
        <div className="px-4 py-10 text-center">
          <Layers className="mx-auto h-6 w-6 text-subtle" aria-hidden="true" />
          <p className="mt-2 text-sm font-medium text-fg">{t("groups.emptyTitle")}</p>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted">
            {t("groups.emptyBody")}
          </p>
          <Button variant="secondary" size="sm" className="mt-3" onClick={openCreate}>
            <FolderPlus className="h-4 w-4" aria-hidden="true" />
            {t("groups.create")}
          </Button>
        </div>
      ) : (
        <ul>
          {groups.data?.items.map((group) => (
            <li
              key={group.id}
              className="flex items-center gap-3 border-b border-border px-4 py-3 transition-colors last:border-b-0 hover:bg-elevated"
            >
              <Layers className="h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-fg" title={group.name}>
                  {group.name}
                </p>
                <p className="text-2xs text-subtle">
                  {t("groups.fileCount", { n: group.files.length })}
                  {group.date_created
                    ? ` · ${t("groups.createdAt", { date: group.date_created })}`
                    : ""}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`${t("common.edit")} · ${group.name}`}
                onClick={() => openEdit(group)}
              >
                <Pencil className="h-4 w-4" aria-hidden="true" />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`${t("common.delete")} · ${group.name}`}
                onClick={() => setDeleteTarget(group)}
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={editor !== null} onOpenChange={(open) => !open && setEditor(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editor?.mode === "edit" ? t("groups.edit") : t("groups.create")}
            </DialogTitle>
            <DialogDescription>{t("groups.emptyBody")}</DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div>
              <label
                htmlFor="group-name"
                className="mb-1 block text-sm font-medium text-fg"
              >
                {t("groups.name")}
              </label>
              <Input
                id="group-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={t("groups.namePlaceholder")}
                maxLength={40}
                autoFocus
              />
            </div>

            <div>
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-fg">{t("groups.files")}</span>
                <span className="text-2xs text-subtle">
                  {t("groups.selected", { n: selected.length })}
                </span>
              </div>
              <div className="relative mb-2">
                <Search
                  className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-subtle"
                  aria-hidden="true"
                />
                <Input
                  value={fileSearch}
                  onChange={(event) => setFileSearch(event.target.value)}
                  placeholder={t("groups.searchFiles")}
                  aria-label={t("groups.searchFiles")}
                  className="h-8 pl-8 text-sm"
                />
              </div>

              {rows.length === 0 ? (
                <p className="rounded-sm border border-dashed border-border bg-elevated/40 p-3 text-sm text-muted">
                  {t("groups.filesEmpty")}
                </p>
              ) : (
                <ul className="scroll-thin max-h-56 space-y-0.5 overflow-y-auto rounded-sm border border-border p-1">
                  {visibleFiles.map((file) => {
                    const checked = selected.includes(file.file_id);
                    return (
                      <li key={file.file_id}>
                        <label
                          className={cn(
                            "flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm",
                            checked ? "bg-accent/[0.06]" : "hover:bg-elevated",
                          )}
                        >
                          <input
                            type="checkbox"
                            className="h-4 w-4 accent-accent"
                            checked={checked}
                            onChange={() => toggleFile(file.file_id)}
                          />
                          <FileTypeIcon type={file.type || file.name} />
                          <span className="min-w-0 flex-1 truncate text-fg">
                            {file.name}
                          </span>
                        </label>
                      </li>
                    );
                  })}
                  {visibleFiles.length === 0 ? (
                    <li className="px-2 py-3 text-center text-sm text-muted">
                      {t("files.noMatch")}
                    </li>
                  ) : null}
                </ul>
              )}
            </div>

            {dialogError ? (
              <p role="alert" className="text-sm text-danger">
                {dialogError}
              </p>
            ) : null}
          </div>

          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setEditor(null)}>
              {t("common.cancel")}
            </Button>
            <Button variant="primary" onClick={() => void save()} disabled={saving}>
              {saving ? t("settings.saving") : t("groups.save")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={t("groups.deleteTitle")}
        description={t("groups.deleteDescription", { name: deleteTarget?.name ?? "" })}
        pending={deleteGroup.isPending}
        onConfirm={() => void confirmDelete()}
      />
    </section>
  );
}
