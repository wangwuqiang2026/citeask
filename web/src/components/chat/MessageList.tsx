import {
  AlertTriangle,
  ChevronDown,
  Copy,
  Loader2,
  Network,
  RotateCcw,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";

import { Markdown } from "@/components/chat/Markdown";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n";
import type { ChatMessage, ConversationDetail, EvidenceItem } from "@/lib/types";
import { cn, formatDateLabel } from "@/lib/utils";

export type StreamPhase = "idle" | "thinking" | "streaming" | "error";

export interface ActiveCitation {
  messageIndex: number;
  evidenceIndex: number;
}

interface MessageListProps {
  messages: ChatMessage[];
  evidenceHistory: EvidenceItem[][];
  /** Mind-map markdown per message index; `null`/missing means "no map". */
  mindmaps?: (string | null)[];
  conversation?: ConversationDetail;
  phase: StreamPhase;
  error: string | null;
  suggestions: string[];
  onSuggestion: (text: string) => void;
  activeCitation: ActiveCitation | null;
  onCitation: (messageIndex: number, evidenceIndex: number) => void;
  onRegenerate: () => void;
  onRetry: () => void;
  onFeedback: (messageIndex: number, liked: boolean, value: string) => void;
}

function dayKey(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toDateString();
}

function DateDivider({ label }: { label: string }) {
  return (
    <div className="my-6 flex items-center gap-3" role="separator" aria-label={label}>
      <span className="h-px flex-1 bg-border" />
      <span className="text-2xs font-medium uppercase tracking-wide text-subtle">
        {label}
      </span>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

function Thinking() {
  const t = useT();
  return (
    <div aria-live="polite">
      <div className="flex items-center gap-2 text-sm text-subtle">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        {t("chat.thinking")}
      </div>
      <div className="mt-3 space-y-2">
        <Skeleton className="h-3 w-3/4" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-2/3" />
      </div>
    </div>
  );
}

function MindmapBlock({ markdown }: { markdown: string }) {
  const t = useT();
  return (
    <details className="mt-3 max-w-[72ch] rounded-lg border border-border bg-panel [&[open]>summary>svg]:rotate-180">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm text-fg marker:hidden [&::-webkit-details-marker]:hidden">
        <Network className="h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
        <span className="flex-1 font-medium">{t("chat.mindmap")}</span>
        <ChevronDown
          className="h-4 w-4 shrink-0 text-subtle transition-transform"
          aria-hidden="true"
        />
      </summary>
      <div className="border-t border-border px-3 py-2">
        <Markdown content={markdown} citationLabel={t("evidence.title")} />
      </div>
    </details>
  );
}

export function MessageList({
  messages,
  evidenceHistory,
  mindmaps = [],
  conversation,
  phase,
  error,
  suggestions,
  onSuggestion,
  activeCitation,
  onCitation,
  onRegenerate,
  onRetry,
  onFeedback,
}: MessageListProps) {
  const t = useT();
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);

  const dateLabels = useMemo(() => {
    let previous = "";
    return messages.map((message, index) => {
      const raw =
        message.created_at ??
        (index === 0 ? conversation?.date_created : undefined) ??
        (index === 0 ? conversation?.date_updated : undefined);
      const key = dayKey(raw);
      if (!key || key === previous) return null;
      previous = key;
      return formatDateLabel(raw as string);
    });
  }, [messages, conversation?.date_created, conversation?.date_updated]);

  const lastAssistantIndex = useMemo(
    () => messages.map((message) => message.role).lastIndexOf("assistant"),
    [messages],
  );

  useEffect(() => {
    if (stickRef.current) {
      bottomRef.current?.scrollIntoView({ block: "end" });
    }
  }, [messages, phase, suggestions]);

  const onScroll = () => {
    const element = scrollRef.current;
    if (!element) return;
    stickRef.current =
      element.scrollHeight - element.scrollTop - element.clientHeight < 96;
  };

  const copy = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      toast.success(t("common.copied"));
    } catch {
      toast.error(t("toast.copyFailed"));
    }
  };

  return (
    <div
      ref={scrollRef}
      onScroll={onScroll}
      className="scroll-thin min-h-0 flex-1 overflow-y-auto"
    >
      <div className="mx-auto w-full max-w-3xl px-4 pb-8 pt-6 md:px-6">
        {messages.map((message, messageIndex) => {
          const label = dateLabels[messageIndex];
          const isAssistant = message.role === "assistant";
          const isLast = messageIndex === messages.length - 1;
          const isStreamingHere = phase !== "idle" && isLast && isAssistant;
          const showThinking =
            isStreamingHere && (phase === "thinking" || message.content.length === 0);
          const evidence = evidenceHistory[messageIndex] ?? [];
          const mindmap = mindmaps[messageIndex] ?? null;

          return (
            <div key={`${message.role}-${messageIndex}`}>
              {label ? <DateDivider label={label} /> : null}

              {isAssistant ? (
                <div className="group mb-6">
                  <div
                    className={cn(
                      "max-w-[72ch] text-fg",
                      isStreamingHere && message.content.length > 0 && "streaming",
                    )}
                  >
                    {showThinking ? (
                      <Thinking />
                    ) : (
                      <Markdown
                        content={message.content}
                        citationLabel={t("evidence.title")}
                        activeCitation={
                          activeCitation?.messageIndex === messageIndex
                            ? activeCitation.evidenceIndex
                            : null
                        }
                        onCitation={(evidenceIndex) =>
                          onCitation(messageIndex, evidenceIndex)
                        }
                      />
                    )}
                  </div>

                  {!showThinking && mindmap ? <MindmapBlock markdown={mindmap} /> : null}

                  {phase === "error" && isLast ? (
                    <div
                      role="alert"
                      className="mt-3 flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
                    >
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">{t("chat.error")}</p>
                        <p className="mt-0.5 text-danger/90">{error}</p>
                      </div>
                      <Button variant="secondary" size="sm" onClick={onRetry}>
                        {t("chat.retry")}
                      </Button>
                    </div>
                  ) : null}

                  {!showThinking && evidence.length > 0 ? (
                    <p className="mt-2 text-2xs text-subtle">
                      {t("chat.evidenceHint", {
                        n: evidence.length,
                        cited: evidence.filter((item) => item.cited).length,
                      })}
                    </p>
                  ) : null}

                  {!isStreamingHere && message.content.length > 0 ? (
                    <div className="mt-1.5 flex items-center gap-0.5 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={t("common.copy")}
                        onClick={() => void copy(message.content)}
                      >
                        <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                      </Button>
                      {isLast ? (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={t("chat.regenerate")}
                          onClick={onRegenerate}
                        >
                          <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                        </Button>
                      ) : null}
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`${t("chat.actions")} 👍`}
                        onClick={() => onFeedback(messageIndex, true, "like")}
                      >
                        <ThumbsUp className="h-3.5 w-3.5" aria-hidden="true" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`${t("chat.actions")} 👎`}
                        onClick={() => onFeedback(messageIndex, false, "dislike")}
                      >
                        <ThumbsDown className="h-3.5 w-3.5" aria-hidden="true" />
                      </Button>
                    </div>
                  ) : null}

                  {isLast && phase === "idle" && suggestions.length > 0 ? (
                    <div className="mt-4">
                      <p className="mb-2 text-2xs font-medium uppercase tracking-wide text-subtle">
                        {t("chat.followups")}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {suggestions.map((suggestion) => (
                          <button
                            key={suggestion}
                            type="button"
                            onClick={() => onSuggestion(suggestion)}
                            className="rounded-full border border-border bg-panel px-3 py-1.5 text-sm text-fg transition-colors hover:border-accent/40 hover:bg-elevated"
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="mb-6 flex justify-end">
                  <div className="max-w-[min(72ch,88%)] whitespace-pre-wrap break-words rounded-lg rounded-br-md bg-accent-soft px-4 py-2.5 text-md leading-relaxed text-fg">
                    {message.content}
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {phase === "error" && lastAssistantIndex === -1 ? (
          <div
            role="alert"
            className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
          >
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            <span className="flex-1">{error}</span>
            <Button variant="secondary" size="sm" onClick={onRetry}>
              {t("chat.retry")}
            </Button>
          </div>
        ) : null}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
