import {
  MessagesSquare,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  useRenameConversation,
} from "@/hooks/use-api";
import { useT } from "@/lib/i18n";
import type { ConversationSummary } from "@/lib/types";
import { cn, groupConversations } from "@/lib/utils";

interface ConversationSidebarProps {
  activeId?: string;
  /** Called after navigating (used to close the mobile drawer). */
  onNavigate?: () => void;
}

export function ConversationSidebar({ activeId, onNavigate }: ConversationSidebarProps) {
  const t = useT();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [renameTarget, setRenameTarget] = useState<ConversationSummary | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<ConversationSummary | null>(null);

  const { data, isLoading, isError } = useConversations();
  const createConversation = useCreateConversation();
  const renameConversation = useRenameConversation();
  const deleteConversation = useDeleteConversation();

  const groups = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const items = (data?.items ?? []).filter((item) =>
      needle ? item.name.toLowerCase().includes(needle) : true,
    );
    return groupConversations(items);
  }, [data?.items, search]);

  const total = data?.items.length ?? 0;

  const newChat = async () => {
    const summary = await createConversation.mutateAsync();
    toast.success(t("toast.created"));
    onNavigate?.();
    navigate(`/chat/${summary.id}`);
  };

  const openRename = (conversation: ConversationSummary) => {
    setRenameTarget(conversation);
    setRenameValue(conversation.name);
  };

  const submitRename = async () => {
    if (!renameTarget) return;
    const name = renameValue.trim();
    if (!name) return;
    await renameConversation.mutateAsync({ id: renameTarget.id, name });
    toast.success(t("toast.renamed"));
    setRenameTarget(null);
  };

  const submitDelete = async () => {
    if (!deleteTarget) return;
    await deleteConversation.mutateAsync(deleteTarget.id);
    toast.success(t("toast.deleted"));
    if (activeId === deleteTarget.id) {
      onNavigate?.();
      navigate("/chat");
    }
    setDeleteTarget(null);
  };

  return (
    <aside
      aria-label={t("a11y.sidebar")}
      className="flex h-full min-h-0 flex-col bg-panel"
    >
      <div className="space-y-2 px-3 pb-2 pt-3">
        <Button
          variant="primary"
          className="w-full justify-start"
          onClick={() => void newChat()}
          disabled={createConversation.isPending}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          {t("chat.newChat")}
        </Button>

        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-subtle"
            aria-hidden="true"
          />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("chat.searchPlaceholder")}
            aria-label={t("chat.searchPlaceholder")}
            className="h-8 pl-8 text-sm"
          />
        </div>
      </div>

      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {isLoading ? (
          <div className="space-y-2 p-2">
            <Skeleton className="h-7 w-full" />
            <Skeleton className="h-7 w-5/6" />
            <Skeleton className="h-7 w-full" />
            <Skeleton className="h-7 w-2/3" />
          </div>
        ) : isError ? (
          <p className="px-2 py-3 text-sm text-danger">{t("error.generic")}</p>
        ) : total === 0 ? (
          <p className="px-2 py-6 text-center text-sm text-muted">{t("chat.emptyBody")}</p>
        ) : groups.length === 0 ? (
          <p className="px-2 py-6 text-center text-sm text-muted">{t("chat.noResults")}</p>
        ) : (
          groups.map((group) => (
            <section key={group.key} aria-label={t(group.key)}>
              <h2 className="px-2 pb-1 pt-3 text-2xs font-medium uppercase tracking-wide text-subtle">
                {t(group.key)}
              </h2>
              <ul>
                {group.items.map((conversation) => {
                  const active = conversation.id === activeId;
                  return (
                    <li key={conversation.id} className="group relative">
                      <button
                        type="button"
                        aria-current={active ? "page" : undefined}
                        onClick={() => {
                          onNavigate?.();
                          navigate(`/chat/${conversation.id}`);
                        }}
                        title={conversation.preview ?? conversation.name}
                        className={cn(
                          "flex w-full items-center gap-2 rounded-sm py-2 pl-2 pr-11 text-left text-sm transition-colors",
                          active
                            ? "bg-elevated text-fg"
                            : "text-muted hover:bg-elevated hover:text-fg",
                        )}
                      >
                        <MessagesSquare
                          className="h-3.5 w-3.5 shrink-0 text-subtle"
                          aria-hidden="true"
                        />
                        <span className="min-w-0 flex-1 truncate">{conversation.name}</span>
                        {conversation.is_public ? (
                          <span className="shrink-0 text-2xs text-subtle">·</span>
                        ) : null}
                      </button>

                      <div className="absolute right-0.5 top-1/2 -translate-y-1/2 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label={`${conversation.name} ${t("common.more")}`}
                            >
                              <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onSelect={() => openRename(conversation)}>
                              <Pencil className="h-4 w-4" aria-hidden="true" />
                              {t("chat.rename")}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onSelect={() => setDeleteTarget(conversation)}
                              className="text-danger data-[highlighted]:bg-danger/10"
                            >
                              <Trash2 className="h-4 w-4" aria-hidden="true" />
                              {t("chat.delete")}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))
        )}
      </div>

      <Dialog
        open={renameTarget !== null}
        onOpenChange={(open) => (open ? undefined : setRenameTarget(null))}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{t("chat.renameTitle")}</DialogTitle>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={(event) => setRenameValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void submitRename();
            }}
            placeholder={t("chat.renamePlaceholder")}
            aria-label={t("chat.renamePlaceholder")}
            autoFocus
          />
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setRenameTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="primary"
              onClick={() => void submitRename()}
              disabled={renameConversation.isPending || renameValue.trim().length === 0}
            >
              {t("common.save")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => (open ? undefined : setDeleteTarget(null))}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{t("chat.deleteTitle")}</DialogTitle>
            <DialogDescription>
              {t("chat.deleteDescription", { name: deleteTarget?.name ?? "" })}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="danger"
              onClick={() => void submitDelete()}
              disabled={deleteConversation.isPending}
            >
              {t("chat.delete")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </aside>
  );
}
