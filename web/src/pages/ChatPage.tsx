import {
  AlertTriangle,
  PanelLeft,
  PanelRight,
  Pencil,
  Plus,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { toast } from "sonner";

import { Composer } from "@/components/chat/Composer";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { EmptyChat } from "@/components/chat/EmptyChat";
import { EvidenceDrawer } from "@/components/chat/EvidenceDrawer";
import { FilePickerDialog } from "@/components/chat/FilePickerDialog";
import { MessageList, type ActiveCitation } from "@/components/chat/MessageList";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useMediaQuery } from "@/hooks/use-media-query";
import {
  useConversation,
  useCreateConversation,
  useFeedback,
  useMeta,
  useRenameConversation,
} from "@/hooks/use-api";
import { useChatStream } from "@/hooks/use-chat-stream";
import type { FileOption } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { Choice, ConversationDetail, SelectionMode } from "@/lib/types";
import { useChatSettings } from "@/stores/chat-settings";
import { useUiStore } from "@/stores/ui";

function choiceLabel(choices: Choice[] | undefined, value: string | undefined): string {
  if (!choices) return value ?? "";
  return choices.find((choice) => choice.value === value)?.label ?? value ?? "";
}

interface ChatSessionProps {
  conversationId?: string;
}

function ChatSession({ conversationId }: ChatSessionProps) {
  const t = useT();
  const navigate = useNavigate();
  const location = useLocation();
  const { data: meta } = useMeta();
  const { data: conversation, isLoading, isError } = useConversation(conversationId);
  const createConversation = useCreateConversation();
  const renameConversation = useRenameConversation();
  const feedback = useFeedback();

  const settings = useChatSettings();
  const sidebarOpen = useUiStore((state) => state.sidebarOpen);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const evidenceOpen = useUiStore((state) => state.evidenceOpen);
  const setEvidenceOpen = useUiStore((state) => state.setEvidenceOpen);
  const setSettingsOpen = useUiStore((state) => state.setSettingsOpen);

  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const dockedEvidence = useMediaQuery("(min-width: 1280px)");
  const setSidebarOpen = useUiStore((state) => state.setSidebarOpen);

  // Below 1024px the conversation list and the evidence panel are overlays; start
  // both closed so they do not cover the chat on first paint. The stored
  // preference still applies on wide screens, and the header buttons open them.
  useEffect(() => {
    if (!isDesktop) {
      setSidebarOpen(false);
      setEvidenceOpen(false);
    }
  }, [isDesktop, setSidebarOpen, setEvidenceOpen]);

  const [pendingFiles, setPendingFiles] = useState<FileOption[]>([]);
  const [filePickerOpen, setFilePickerOpen] = useState(false);
  const [activeCitation, setActiveCitation] = useState<ActiveCitation | null>(null);
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState("");

  const indexId = meta?.indices?.[0]?.id;
  const selectionMode: SelectionMode = pendingFiles.length
    ? "select"
    : settings.selectionMode;
  // `meta.features.mindmap` is a capability flag, not a default: follow it when
  // the user has not chosen, and always send an explicit boolean.
  const mindmapOn = settings.mindmap ?? Boolean(meta?.features.mindmap);

  useEffect(() => {
    if (meta) useChatSettings.getState().hydrate(meta);
  }, [meta]);

  const buildBody = useMemo(
    () => (message: string, regenerate: boolean) => ({
      message,
      selection:
        indexId !== undefined
          ? {
              [String(indexId)]: {
                mode: selectionMode,
                file_ids: pendingFiles.map((file) => file.id),
              },
            }
          : {},
      overrides: {
        reasoning: settings.reasoning ?? null,
        llm: settings.llm ?? "",
        language: settings.language ?? null,
        citation: settings.citation ?? null,
        mindmap: mindmapOn,
      },
      regenerate,
    }),
    [
      indexId,
      pendingFiles,
      selectionMode,
      settings.reasoning,
      settings.llm,
      settings.language,
      settings.citation,
      mindmapOn,
    ],
  );

  const stream = useChatStream({ conversationId, conversation, buildBody });
  const sendRef = useRef(stream.send);
  useEffect(() => {
    sendRef.current = stream.send;
  }, [stream.send]);

  const name = stream.title ?? conversation?.name ?? t("chat.newChat");

  useEffect(() => {
    setActiveCitation(null);
  }, [conversationId]);

  const lastAssistantIndex = useMemo(
    () => stream.messages.map((message) => message.role).lastIndexOf("assistant"),
    [stream.messages],
  );

  const viewIndex = stream.evidenceView ?? lastAssistantIndex;
  const evidenceItems = viewIndex >= 0 ? (stream.evidenceHistory[viewIndex] ?? []) : [];

  const autoOpenedRef = useRef(false);
  useEffect(() => {
    // On a wide screen the docked panel is a side column, so opening it with the
    // first evidence item costs nothing. On narrow screens it is an overlay that
    // would hide the answer: leave it to the header button there.
    if (
      isDesktop &&
      stream.isActive &&
      evidenceItems.length > 0 &&
      !autoOpenedRef.current
    ) {
      autoOpenedRef.current = true;
      setEvidenceOpen(true);
    }
    if (!stream.isActive) autoOpenedRef.current = false;
  }, [isDesktop, stream.isActive, evidenceItems.length, setEvidenceOpen]);

  // A message typed on /chat creates the conversation and re-enters the route;
  // the new session picks the text up from the router state and sends it once.
  const pendingRef = useRef<string | null>(null);
  const locationState = location.state as { pending?: string } | null;
  useEffect(() => {
    if (pendingRef.current === null && locationState?.pending) {
      pendingRef.current = locationState.pending;
    }
  }, [locationState]);
  useEffect(() => {
    if (!pendingRef.current || !conversationId || !conversation) return;
    const text = pendingRef.current;
    pendingRef.current = null;
    void sendRef.current(text);
    navigate(location.pathname, { replace: true, state: null });
  }, [conversationId, conversation, navigate, location.pathname]);

  const send = async (text: string) => {
    if (conversationId) {
      void stream.send(text);
      return;
    }
    try {
      const created = await createConversation.mutateAsync();
      navigate(`/chat/${created.id}`, { replace: true, state: { pending: text } });
    } catch {
      toast.error(t("error.generic"));
    }
  };

  const newChat = async () => {
    try {
      const created = await createConversation.mutateAsync();
      toast.success(t("toast.created"));
      navigate(`/chat/${created.id}`);
    } catch {
      toast.error(t("error.generic"));
    }
  };

  const submitRename = async () => {
    if (!conversationId) return;
    const value = renameValue.trim();
    if (!value) return;
    try {
      await renameConversation.mutateAsync({ id: conversationId, name: value });
      toast.success(t("toast.renamed"));
      setRenameOpen(false);
    } catch {
      toast.error(t("error.generic"));
    }
  };

  const onFeedback = (messageIndex: number, liked: boolean, value: string) => {
    if (!conversationId) return;
    feedback.mutate(
      { conversationId, messageIndex, liked, value },
      {
        onSuccess: () => toast.success(t("chat.actions")),
        onError: () => toast.error(t("error.generic")),
      },
    );
  };

  const uploadLegacy = () => window.open("/legacy", "_blank", "noopener");

  const scopeLabel = pendingFiles.length
    ? `${t("settings.scopeSelect")} · ${pendingFiles.length}`
    : settings.selectionMode === "select"
      ? t("settings.scopeSelect")
      : settings.selectionMode === "disabled"
        ? t("settings.scopeDisabled")
        : t("settings.scopeAll");

  const header = (
    <header className="flex h-14 shrink-0 items-center gap-1 border-b border-border px-2.5">
      <Button
        variant="ghost"
        size="icon"
        aria-label={t("a11y.sidebar")}
        onClick={toggleSidebar}
      >
        <PanelLeft className="h-4 w-4" aria-hidden="true" />
      </Button>

      <div className="min-w-0 flex-1">
        <button
          type="button"
          onClick={() => {
            setRenameValue(name);
            setRenameOpen(true);
          }}
          title={t("chat.renameTitle")}
          className="group flex max-w-full items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-left transition-colors hover:bg-elevated"
        >
          <span className="truncate text-md font-medium text-fg">{name}</span>
          <Pencil
            className="h-3 w-3 shrink-0 text-subtle opacity-0 transition-opacity group-hover:opacity-100"
            aria-hidden="true"
          />
        </button>
      </div>

      {conversation?.is_public ? (
        <Badge variant="outline">{t("chat.public")}</Badge>
      ) : null}

      <Button
        variant="ghost"
        size="icon"
        aria-label={t("evidence.toggle")}
        aria-pressed={evidenceOpen}
        onClick={() => setEvidenceOpen(!evidenceOpen)}
        className="relative"
      >
        <PanelRight className="h-4 w-4" aria-hidden="true" />
        {evidenceItems.length > 0 ? (
          <span className="absolute right-0.5 top-0.5 rounded-full bg-accent px-1 text-[10px] font-semibold leading-4 text-accent-fg">
            {evidenceItems.length}
          </span>
        ) : null}
      </Button>

      <Button
        variant="ghost"
        size="icon"
        aria-label={t("settings.title")}
        onClick={() => setSettingsOpen(true)}
      >
        <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
      </Button>

      {/* The sidebar already offers "new conversation"; keep the header copy only
          when the sidebar is collapsed or the viewport is too narrow for it. */}
      {!isDesktop || !sidebarOpen ? (
        <Button variant="primary" size="sm" onClick={() => void newChat()}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">{t("chat.newChat")}</span>
        </Button>
      ) : null}
    </header>
  );

  return (
    <div className="relative flex min-h-0 min-w-0 flex-1">
      <PanelGroup
        direction="horizontal"
        autoSaveId="citeask.chat.layout"
        className="min-h-0 min-w-0 flex-1"
      >
        {isDesktop && sidebarOpen ? (
          <>
            <Panel id="sidebar" order={1} defaultSize={20} minSize={17} maxSize={27}>
              <ConversationSidebar activeId={conversationId} />
            </Panel>
            <PanelResizeHandle aria-label={t("a11y.resize")} />
          </>
        ) : null}

        <Panel id="main" order={2} minSize={40} className="flex min-h-0 min-w-0 flex-col bg-panel">
          {header}

          {stream.warning ? (
            <div
              role="status"
              className="flex items-start gap-2 border-b border-border bg-accent-soft px-4 py-2 text-sm text-muted"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
              <span className="flex-1">{stream.warning}</span>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={t("common.close")}
                onClick={stream.clearWarning}
              >
                <X className="h-3.5 w-3.5" aria-hidden="true" />
              </Button>
            </div>
          ) : null}

          <div className="flex min-h-0 flex-1 flex-col">
            {isLoading ? (
              <div className="mx-auto w-full max-w-3xl space-y-4 px-6 py-8">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-10 w-1/2" />
              </div>
            ) : isError ? (
              <div className="mx-auto mt-10 w-full max-w-lg rounded-md border border-danger/30 bg-danger/10 p-4 text-sm text-danger">
                <p className="font-medium">{t("error.conversationMissing")}</p>
                <Button variant="secondary" size="sm" className="mt-3" onClick={() => navigate("/chat")}>
                  {t("chat.newChat")}
                </Button>
              </div>
            ) : stream.messages.length === 0 && !stream.isActive ? (
              <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
                <EmptyChat
                  suggestions={[t("chat.suggest1"), t("chat.suggest2"), t("chat.suggest3")]}
                  onSuggestion={(text) => void send(text)}
                  onUpload={uploadLegacy}
                  onChooseFiles={() => setFilePickerOpen(true)}
                />
              </div>
            ) : (
              <MessageList
                messages={stream.messages}
                evidenceHistory={stream.evidenceHistory}
                mindmaps={stream.mindmaps}
                conversation={conversation as ConversationDetail | undefined}
                phase={stream.phase}
                error={stream.error}
                suggestions={stream.suggestions}
                onSuggestion={(text) => void send(text)}
                activeCitation={activeCitation}
                onCitation={(messageIndex, evidenceIndex) => {
                  setActiveCitation({ messageIndex, evidenceIndex });
                  setEvidenceOpen(true);
                }}
                onRegenerate={() => void stream.send("", { regenerate: true })}
                onRetry={() => void stream.send("", { regenerate: true })}
                onFeedback={onFeedback}
              />
            )}
          </div>

          <Composer
            onSend={(text) => void send(text)}
            streaming={stream.isActive}
            onStop={stream.stop}
            disabled={!meta}
            pendingFiles={pendingFiles}
            onRemoveFile={(fileId) =>
              setPendingFiles((current) => current.filter((file) => file.id !== fileId))
            }
            onOpenFilePicker={() => setFilePickerOpen(true)}
            onUploadLegacy={uploadLegacy}
            onOpenSettings={() => setSettingsOpen(true)}
            reasoningLabel={choiceLabel(meta?.reasoning.choices, settings.reasoning)}
            modelLabel={
              settings.llm
                ? choiceLabel(meta?.models.choices, settings.llm)
                : t("chat.defaultModel")
            }
            languageLabel={choiceLabel(meta?.languages.choices, settings.language)}
            citationLabel={choiceLabel(meta?.citations.choices, settings.citation)}
            scopeLabel={scopeLabel}
            mindmapOn={mindmapOn}
          />
        </Panel>

        {dockedEvidence && evidenceOpen ? (
          <>
            <PanelResizeHandle aria-label={t("a11y.resize")} />
            <Panel id="evidence" order={3} defaultSize={26} minSize={20} maxSize={34}>
              <EvidenceDrawer
                items={evidenceItems}
                activeIndex={
                  activeCitation && activeCitation.messageIndex === viewIndex
                    ? activeCitation.evidenceIndex
                    : null
                }
                onClose={() => setEvidenceOpen(false)}
              />
            </Panel>
          </>
        ) : null}
      </PanelGroup>

      {!isDesktop && sidebarOpen ? (
        <div className="fixed inset-0 z-40">
          <button
            type="button"
            aria-label={t("common.close")}
            className="absolute inset-0 bg-black/35"
            onClick={toggleSidebar}
          />
          <div className="absolute inset-y-0 left-0 z-10 w-[min(320px,85vw)] border-r border-border bg-panel shadow-pop">
            <ConversationSidebar
              activeId={conversationId}
              onNavigate={() => useUiStore.getState().toggleSidebar()}
            />
          </div>
        </div>
      ) : null}

      {!dockedEvidence && evidenceOpen ? (
        <div className="fixed inset-0 z-40">
          <button
            type="button"
            aria-label={t("common.close")}
            className="absolute inset-0 bg-black/35"
            onClick={() => setEvidenceOpen(false)}
          />
          <div className="absolute inset-y-0 right-0 z-10 w-[min(380px,92vw)] border-l border-border bg-panel shadow-pop">
            <EvidenceDrawer
              items={evidenceItems}
              activeIndex={
                activeCitation && activeCitation.messageIndex === viewIndex
                  ? activeCitation.evidenceIndex
                  : null
              }
              onClose={() => setEvidenceOpen(false)}
            />
          </div>
        </div>
      ) : null}

      <FilePickerDialog
        open={filePickerOpen}
        onOpenChange={setFilePickerOpen}
        onConfirm={(files) => setPendingFiles(files)}
        indexId={indexId}
      />

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
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
            aria-label={t("chat.renamePlaceholder")}
            placeholder={t("chat.renamePlaceholder")}
            autoFocus
          />
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setRenameOpen(false)}>
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
    </div>
  );
}

export function ChatPage() {
  const { id } = useParams<{ id: string }>();
  return <ChatSession key={id ?? "new"} conversationId={id} />;
}
