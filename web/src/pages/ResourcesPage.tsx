import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  CircleAlert,
  ExternalLink,
  FolderOpen,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { PageFrame } from "@/components/app/PageFrame";
import { ConfirmDialog } from "@/components/files/ConfirmDialog";
import { McpDialog } from "@/components/resources/McpDialog";
import { VendorDialog } from "@/components/resources/VendorDialog";
import { Badge } from "@/components/ui/badge";
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
import { Switch } from "@/components/ui/switch";
import { useMeta } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query";
import type { User, VendorEntry } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useChatSettings } from "@/stores/chat-settings";

type TabKey = "indices" | "models" | "users";

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "border-b-2 px-3 py-2 text-sm transition-colors",
        active
          ? "border-accent text-fg"
          : "border-transparent text-muted hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

function Section({
  title,
  count,
  actions,
  children,
}: {
  title: string;
  count?: number;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-md border border-border bg-panel">
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
        <h2 className="text-sm font-medium text-fg">{title}</h2>
        <div className="flex items-center gap-2">
          {count !== undefined ? (
            <span className="text-2xs text-subtle">{count}</span>
          ) : null}
          {actions}
        </div>
      </header>
      {children}
    </section>
  );
}

type PoolRow = {
  name: string;
  vendor?: string;
  model?: string;
  default?: boolean;
  /** Set by the server: the model the index actually runs on (read-only pools). */
  in_use?: boolean;
};

function ModelPool({
  title,
  rows,
  canEdit,
  addLabel,
  currentName,
  busy = false,
  onUse,
  onAdd,
  onEdit,
  onRemove,
}: {
  title: string;
  rows: PoolRow[];
  canEdit: boolean;
  addLabel?: string;
  /** The model this account's chat runs on (LLM pool only). */
  currentName?: string;
  /** A rebuild is running: adding/switching models now would race with it. */
  busy?: boolean;
  onUse?: (row: PoolRow) => void;
  onAdd?: () => void;
  onEdit?: (row: PoolRow) => void;
  onRemove?: (row: PoolRow) => void;
}) {
  const t = useT();
  const addTitle = addLabel ?? t("resources.addModel");
  return (
    <Section
      title={title}
      count={rows.length}
      actions={
        canEdit && onAdd ? (
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={addTitle}
            title={addTitle}
            disabled={busy}
            onClick={onAdd}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
          </Button>
        ) : null
      }
    >
      {rows.length === 0 ? (
        <p className="px-4 py-3 text-sm text-subtle">{t("resources.empty")}</p>
      ) : (
        <ul className="divide-y divide-border">
          {rows.map((row) => {
            const inUse =
              row.in_use ?? (Boolean(currentName) && row.name === currentName);
            return (
              <li
                key={row.name}
                className="flex flex-wrap items-center gap-2 px-4 py-2.5"
              >
                <span className="min-w-0 flex-1 truncate text-sm text-fg">
                  {row.name}
                </span>
                {row.default ? (
                  <Badge variant="accent">{t("resources.defaultBadge")}</Badge>
                ) : null}
                {inUse ? (
                  <Badge variant="success">{t("resources.inUse")}</Badge>
                ) : null}
                {row.vendor ? <Badge variant="outline">{row.vendor}</Badge> : null}
                {row.model ? (
                  <span className="max-w-[40%] truncate text-2xs text-subtle">
                    {row.model}
                  </span>
                ) : null}
                {onUse && !inUse ? (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={t("resources.useModel")}
                    title={t("resources.useModel")}
                    disabled={busy}
                    onClick={() => onUse(row)}
                  >
                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                  </Button>
                ) : null}
                {canEdit ? (
                  <div className="flex shrink-0 gap-1">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={t("resources.editModel")}
                      title={t("resources.editModel")}
                      onClick={() => onEdit?.(row)}
                    >
                      <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={t("common.delete")}
                      title={t("common.delete")}
                      onClick={() => onRemove?.(row)}
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    </Button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

interface UserDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: User | null;
  onSaved: () => void;
}

function UserDialog({ open, onOpenChange, user, onSaved }: UserDialogProps) {
  const t = useT();
  const editing = user !== null;

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [admin, setAdmin] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setUsername(user?.username ?? "");
    setPassword("");
    setConfirm("");
    setAdmin(user?.admin ?? false);
    setError(null);
  }, [open, user]);

  const mutation = useMutation({
    mutationFn: () =>
      editing
        ? api.updateUser(user.id, {
            username,
            admin,
            ...(password ? { password } : {}),
          })
        : api.createUser({ username, password, admin }),
    onSuccess: () => {
      onOpenChange(false);
      onSaved();
    },
    onError: (mutationError: Error) => setError(mutationError.message),
  });

  const submit = () => {
    if (!username.trim()) {
      setError(t("resources.username"));
      return;
    }
    if (!editing && !password) {
      setError(t("resources.passwordHelp"));
      return;
    }
    if (password && password !== confirm) {
      setError(t("resources.passwordMismatch"));
      return;
    }
    mutation.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>
            {editing ? t("resources.editUser") : t("resources.createUser")}
          </DialogTitle>
          <DialogDescription>{t("resources.passwordHelp")}</DialogDescription>
        </DialogHeader>

        <div className="mt-2 space-y-3">
          <label className="block space-y-1">
            <span className="text-sm text-fg">{t("resources.username")}</span>
            <Input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="off"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm text-fg">
              {editing ? t("resources.password") : t("resources.password")}
            </span>
            <Input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              placeholder={editing ? t("resources.password") : ""}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm text-fg">{t("resources.confirmPassword")}</span>
            <Input
              type="password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              autoComplete="new-password"
            />
          </label>
          <div className="flex items-center justify-between gap-4 py-1">
            <span className="text-sm text-fg">{t("resources.admin")}</span>
            <Switch checked={admin} onCheckedChange={setAdmin} />
          </div>
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button variant="primary" onClick={submit} disabled={mutation.isPending}>
            {t("resources.save")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function UsersPanel() {
  const t = useT();
  const queryClient = useQueryClient();
  const { data: meta } = useMeta();
  const me = meta?.user ?? null;

  const usersQuery = useQuery({
    queryKey: queryKeys.users,
    queryFn: () => api.listUsers(),
  });

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);

  const remove = useMutation({
    mutationFn: (user: User) => api.deleteUser(user.id),
    onSuccess: (_data, user) => {
      setDeleteTarget(null);
      toast.success(t("resources.deleted"));
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
      if (user.id === me?.id) void queryClient.invalidateQueries();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const users = usersQuery.data?.items ?? [];

  return (
    <>
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-sm text-muted">{t("resources.usersHint")}</p>
        <Button
          variant="primary"
          size="sm"
          onClick={() => {
            setEditingUser(null);
            setDialogOpen(true);
          }}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          {t("resources.createUser")}
        </Button>
      </div>

      {usersQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : usersQuery.isError ? (
        <p className="flex items-center gap-2 text-sm text-danger" role="alert">
          <CircleAlert className="h-4 w-4" aria-hidden="true" />
          {t("resources.loadError")}
        </p>
      ) : (
        <Section title={t("resources.tabUsers")} count={users.length}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-2xs uppercase tracking-wide text-subtle">
                <th className="px-4 py-2 font-medium">{t("resources.username")}</th>
                <th className="px-4 py-2 font-medium">{t("resources.role")}</th>
                <th className="px-4 py-2 text-right font-medium">
                  {t("resources.indexActions")}
                </th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const self = user.id === me?.id;
                return (
                  <tr key={user.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-2.5">
                      <span className="text-fg">{user.username}</span>
                      {self ? (
                        <span className="ml-2 text-2xs text-subtle">
                          ({t("account.title")})
                        </span>
                      ) : null}
                    </td>
                    <td className="px-4 py-2.5">
                      {user.admin ? (
                        <Badge variant="accent">{t("resources.roleAdmin")}</Badge>
                      ) : (
                        <Badge variant="outline">{t("resources.roleUser")}</Badge>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={t("resources.editUser")}
                          onClick={() => {
                            setEditingUser(user);
                            setDialogOpen(true);
                          }}
                        >
                          <Pencil className="h-4 w-4" aria-hidden="true" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={t("common.delete")}
                          title={self ? t("resources.selfHint") : t("common.delete")}
                          disabled={self}
                          onClick={() => setDeleteTarget(user)}
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Section>
      )}

      <UserDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        user={editingUser}
        onSaved={() => {
          toast.success(editingUser ? t("resources.updated") : t("resources.created"));
          setEditingUser(null);
          void queryClient.invalidateQueries({ queryKey: queryKeys.users });
        }}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title={t("resources.deleteTitle")}
        description={t("resources.deleteDescription", {
          name: deleteTarget?.username ?? "",
        })}
        pending={remove.isPending}
        onConfirm={() => {
          if (deleteTarget) remove.mutate(deleteTarget);
        }}
      />
    </>
  );
}

export function ResourcesPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const { data: meta } = useMeta();
  const isAdmin = Boolean(meta?.user?.admin);
  const [tab, setTab] = useState<TabKey>("indices");

  const resourcesQuery = useQuery({
    queryKey: queryKeys.resources,
    queryFn: () => api.getResources(),
    staleTime: 60_000,
  });
  const resources = resourcesQuery.data;

  const catalogQuery = useQuery({
    queryKey: queryKeys.vendorCatalog,
    queryFn: () => api.getVendorCatalog(),
    staleTime: Infinity,
  });
  const catalog = catalogQuery.data;

  const [vendorDialog, setVendorDialog] = useState<{
    kind: string;
    entry: VendorEntry | null;
  } | null>(null);
  const [mcpDialog, setMcpDialog] = useState<{ entry: VendorEntry | null } | null>(
    null,
  );
  const [removeTarget, setRemoveTarget] = useState<{
    kind: string;
    name: string;
    isDefault: boolean;
  } | null>(null);
  const [embeddingTarget, setEmbeddingTarget] = useState<PoolRow | null>(null);

  const refreshResources = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.resources });
    void queryClient.invalidateQueries({ queryKey: queryKeys.meta });
  };

  // Switching the embedding model drops and rebuilds the index; the server runs
  // that in the background and this poll reports progress (§5.36).
  const embeddingJobQuery = useQuery({
    queryKey: queryKeys.embeddingJob,
    queryFn: () => api.getEmbeddingJob(),
    enabled: isAdmin,
    refetchInterval: (query) =>
      query.state.data?.job.state === "running" ? 1200 : false,
  });
  const job = embeddingJobQuery.data?.job;
  const reindexing = job?.state === "running";
  const lastJobState = useRef<string | null>(null);
  useEffect(() => {
    if (!job) return;
    if (lastJobState.current === null) {
      lastJobState.current = job.state;
      return;
    }
    if (lastJobState.current === job.state) return;
    lastJobState.current = job.state;
    if (job.state === "done") {
      toast.success(job.message || t("resources.reindexDone"));
      refreshResources();
    } else if (job.state === "error") {
      toast.error(job.message || t("resources.reindexError"));
      refreshResources();
    }
  }, [job]); // eslint-disable-line react-hooks/exhaustive-deps

  const switchEmbedding = useMutation({
    mutationFn: (name: string) => api.setEmbedding(name),
    onSuccess: (data) => {
      setEmbeddingTarget(null);
      if (!data.started) {
        toast.info(t("resources.alreadyInUse", { name: data.job.embedding }));
        refreshResources();
        return;
      }
      toast.success(
        t("resources.rebuildStarted", { name: data.job.embedding }),
      );
      queryClient.setQueryData(queryKeys.embeddingJob, { job: data.job });
    },
    onError: (error: Error) => {
      setEmbeddingTarget(null);
      toast.error(error.message);
    },
  });

  // Reranking happens per query, so this switch needs no rebuild (§5.36).
  const switchReranking = useMutation({
    mutationFn: (name: string) => api.setCurrentReranking(name),
    onSuccess: (data) => {
      toast.success(t("resources.switchedTo", { name: data.name }));
      refreshResources();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  // The model this account's chat runs on: persisted in the account, so the
  // resources page, the chat header and every device agree (MODIFICATIONS §5.33).
  const switchLlm = useMutation({
    mutationFn: (name: string) => api.setCurrentLlm(name),
    onSuccess: (data) => {
      useChatSettings.getState().update({ llm: data.name });
      toast.success(t("resources.switchedTo", { name: data.name }));
      refreshResources();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const removeVendor = useMutation({
    mutationFn: (target: { kind: string; name: string }) =>
      api.deleteVendor(target.kind, target.name),
    onSuccess: () => {
      setRemoveTarget(null);
      toast.success(t("resources.resourceDeleted"));
      refreshResources();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const openEdit = async (kind: string, name: string) => {
    try {
      const entry = await api.getVendor(kind, name);
      setVendorDialog({ kind, entry });
    } catch (error) {
      toast.error((error as Error).message);
    }
  };

  const openClassic = () => window.open("/legacy/", "_blank", "noopener");

  return (
    <PageFrame
      wide
      title={t("resources.title")}
      subtitle={t("resources.subtitle")}
      actions={
        <Button variant="secondary" size="sm" onClick={openClassic}>
          <ExternalLink className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">{t("resources.openClassic")}</span>
        </Button>
      }
      footer={
        <div className="flex flex-wrap items-center gap-2 border-t border-border bg-panel px-5 py-2 text-2xs text-subtle">
          <span>{t("resources.indexHint")}</span>
          <button
            type="button"
            onClick={openClassic}
            className="shrink-0 text-accent hover:underline"
          >
            {t("resources.openClassic")}
          </button>
        </div>
      }
    >
      <div className="mb-4 flex gap-1 border-b border-border" role="tablist">
        <TabButton active={tab === "indices"} onClick={() => setTab("indices")}>
          {t("resources.tabIndices")}
        </TabButton>
        <TabButton active={tab === "models"} onClick={() => setTab("models")}>
          {t("resources.tabModels")}
        </TabButton>
        {isAdmin ? (
          <TabButton active={tab === "users"} onClick={() => setTab("users")}>
            {t("resources.tabUsers")}
          </TabButton>
        ) : null}
      </div>

      {resourcesQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : resourcesQuery.isError ? (
        <p className="flex items-center gap-2 text-sm text-danger" role="alert">
          <CircleAlert className="h-4 w-4" aria-hidden="true" />
          {t("resources.loadError")}
        </p>
      ) : !resources ? null : tab === "indices" ? (
        <Section title={t("resources.tabIndices")} count={resources.indices.length}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-2xs uppercase tracking-wide text-subtle">
                <th className="px-4 py-2 font-medium">{t("resources.indexName")}</th>
                <th className="hidden px-4 py-2 font-medium sm:table-cell">
                  {t("resources.indexId")}
                </th>
                <th className="px-4 py-2 font-medium">
                  {t("resources.indexVisibility")}
                </th>
                <th className="px-4 py-2 text-right font-medium">
                  {t("resources.indexFiles")}
                </th>
                <th className="px-4 py-2 text-right font-medium">
                  {t("resources.indexActions")}
                </th>
              </tr>
            </thead>
            <tbody>
              {resources.indices.map((index) => (
                <tr key={String(index.id)} className="border-b border-border last:border-0">
                  <td className="px-4 py-2.5 text-fg">{index.name}</td>
                  <td className="hidden px-4 py-2.5 font-mono text-2xs text-subtle sm:table-cell">
                    {String(index.id)}
                  </td>
                  <td className="px-4 py-2.5">
                    {index.private ? (
                      <Badge variant="outline">{t("resources.private")}</Badge>
                    ) : (
                      <Badge variant="subtle">{t("resources.public")}</Badge>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right text-muted">
                    {index.file_count}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <a
                      href="/files"
                      className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                    >
                      <FolderOpen className="h-3.5 w-3.5" aria-hidden="true" />
                      {t("resources.viewFiles")}
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      ) : tab === "models" ? (
        <div className="space-y-4">
          <p className="text-sm text-muted">{t("resources.modelsHint")}</p>
          <ModelPool
            title={t("resources.llms")}
            rows={resources.llms}
            canEdit={isAdmin}
            currentName={meta?.models.default}
            onUse={(row) => switchLlm.mutate(row.name)}
            onAdd={() => setVendorDialog({ kind: "llms", entry: null })}
            onEdit={(row) => void openEdit("llms", row.name)}
            onRemove={(row) =>
              setRemoveTarget({ kind: "llms", name: row.name, isDefault: !!row.default })
            }
          />
          <p
            className={cn(
              "text-2xs",
              reindexing
                ? "text-accent"
                : job?.state === "error"
                  ? "text-danger"
                  : "text-subtle",
            )}
            role={job?.state === "error" ? "alert" : undefined}
          >
            {reindexing
              ? t("resources.reindexing", {
                  name: job?.embedding ?? "",
                  done: job?.done ?? 0,
                  total: job?.total ?? 0,
                })
              : job?.state === "done" || job?.state === "error"
                ? job.message
                : t("resources.embeddingsHint")}
          </p>
          {job && !reindexing && (job.state === "error" || job.failed > 0) ? (
            <button
              type="button"
              className="text-2xs text-accent hover:underline"
              onClick={() => switchEmbedding.mutate(job.embedding)}
            >
              {t("resources.retryRebuild")}
            </button>
          ) : null}
          <ModelPool
            title={t("resources.embeddings")}
            rows={resources.embeddings}
            canEdit={isAdmin}
            busy={reindexing}
            onUse={(row) => setEmbeddingTarget(row)}
            onAdd={() => setVendorDialog({ kind: "embeddings", entry: null })}
            onEdit={(row) => void openEdit("embeddings", row.name)}
            onRemove={(row) =>
              setRemoveTarget({ kind: "embeddings", name: row.name, isDefault: !!row.default })
            }
          />
          <ModelPool
            title={t("resources.rerankings")}
            rows={resources.rerankings}
            canEdit={isAdmin}
            onUse={(row) => switchReranking.mutate(row.name)}
            onAdd={() => setVendorDialog({ kind: "rerankings", entry: null })}
            onEdit={(row) => void openEdit("rerankings", row.name)}
            onRemove={(row) =>
              setRemoveTarget({ kind: "rerankings", name: row.name, isDefault: !!row.default })
            }
          />
          <ModelPool
            title={t("resources.mcp")}
            rows={resources.mcp}
            canEdit={isAdmin}
            addLabel={t("resources.addMcp")}
            onAdd={() => setMcpDialog({ entry: null })}
            onEdit={async (row) => {
              try {
                const entry = await api.getVendor("mcp", row.name);
                setMcpDialog({ entry });
              } catch (error) {
                toast.error((error as Error).message);
              }
            }}
            onRemove={(row) => setRemoveTarget({ kind: "mcp", name: row.name, isDefault: false })}
          />
        </div>
      ) : (
        <UsersPanel />
      )}

      <VendorDialog
        open={vendorDialog !== null}
        onOpenChange={(open) => {
          if (!open) setVendorDialog(null);
        }}
        kind={vendorDialog?.kind ?? "llms"}
        catalog={
          vendorDialog?.kind === "embeddings"
            ? (catalog?.embeddings ?? [])
            : vendorDialog?.kind === "rerankings"
              ? (catalog?.rerankings ?? [])
              : (catalog?.llms ?? [])
        }
        entry={vendorDialog?.entry ?? null}
        onSaved={() => {
          toast.success(
            vendorDialog?.entry
              ? t("resources.resourceUpdated")
              : t("resources.resourceCreated"),
          );
          refreshResources();
        }}
      />

      <McpDialog
        open={mcpDialog !== null}
        onOpenChange={(open) => {
          if (!open) setMcpDialog(null);
        }}
        entry={mcpDialog?.entry ?? null}
        onSaved={() => {
          toast.success(
            mcpDialog?.entry
              ? t("resources.resourceUpdated")
              : t("resources.resourceCreated"),
          );
          refreshResources();
        }}
      />

      <ConfirmDialog
        open={removeTarget !== null}
        onOpenChange={(open) => {
          if (!open) setRemoveTarget(null);
        }}
        title={t("resources.deleteResourceTitle")}
        description={
          removeTarget?.isDefault
            ? t("resources.deleteDefaultDescription", { name: removeTarget.name })
            : t("resources.deleteResourceDescription", { name: removeTarget?.name ?? "" })
        }
        pending={removeVendor.isPending}
        onConfirm={() => {
          if (removeTarget) removeVendor.mutate(removeTarget);
        }}
      />

      <ConfirmDialog
        open={embeddingTarget !== null}
        onOpenChange={(open) => {
          if (!open) setEmbeddingTarget(null);
        }}
        title={t("resources.switchEmbeddingTitle")}
        description={t("resources.switchEmbeddingDescription", {
          name: embeddingTarget?.name ?? "",
          n: resources?.indices.reduce((sum, index) => sum + index.file_count, 0) ?? 0,
        })}
        confirmLabel={t("resources.switchAndRebuild")}
        pending={switchEmbedding.isPending}
        onConfirm={() => {
          if (embeddingTarget) switchEmbedding.mutate(embeddingTarget.name);
        }}
      />
    </PageFrame>
  );
}
