import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "@/lib/api";
import { queryKeys } from "@/lib/query";
import type {
  ChatMessage,
  ConversationDetail,
  EvidenceItem,
  SendMessageBody,
} from "@/lib/types";

export type StreamPhase = "idle" | "thinking" | "streaming" | "error";

interface UseChatStreamParams {
  conversationId?: string;
  conversation?: ConversationDetail;
  buildBody: (message: string, regenerate: boolean) => SendMessageBody;
}

function isAbort(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  );
}

/**
 * The API stores evidence and mind maps as one entry per Q/A *pair*, while the
 * message list indexes everything by *message* (answers sit on the odd indices).
 * These helpers convert between the two shapes, so a reloaded conversation shows
 * the same evidence panel as a live answer instead of an empty one.
 */
function toMessageIndexed<T>(
  perPair: T[] | undefined,
  messageCount: number,
  empty: T,
): T[] {
  const output: T[] = Array.from({ length: messageCount }, () => empty);
  (perPair ?? []).forEach((value, pair) => {
    const index = pair * 2 + 1;
    if (index < messageCount) output[index] = value;
  });
  return output;
}

function toPairIndexed<T>(perMessage: T[], messageCount: number, empty: T): T[] {
  const output: T[] = [];
  for (let index = 1; index < messageCount; index += 2) {
    output.push(perMessage[index] ?? empty);
  }
  return output;
}

/**
 * Owns the optimistic message list and the SSE lifecycle of one conversation.
 *
 * The server keeps the source of truth; while a stream runs the local state is
 * authoritative (so tokens render immediately), and on completion it is written
 * back into the react-query cache instead of refetching — a refetch racing the
 * final persist would drop the last tokens.
 */
export function useChatStream({
  conversationId,
  conversation,
  buildBody,
}: UseChatStreamParams) {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [evidenceHistory, setEvidenceHistory] = useState<EvidenceItem[][]>([]);
  const [mindmaps, setMindmaps] = useState<(string | null)[]>([]);
  const [phase, setPhase] = useState<StreamPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [title, setTitle] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [evidenceView, setEvidenceView] = useState<number | null>(null);

  const activeRef = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);
  const evidenceRef = useRef<EvidenceItem[][]>([]);
  const mindmapsRef = useRef<(string | null)[]>([]);
  const titleRef = useRef<string | null>(null);
  const conversationRef = useRef<ConversationDetail | undefined>(undefined);
  const mountedRef = useRef(true);

  // Read through the ref so the sync effect below can depend on the conversation
  // *id* only: finishing a stream rewrites the detail object in the query cache,
  // which must not re-run the reset branch and wipe error/suggestions/evidence.
  conversationRef.current = conversation;

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);
  useEffect(() => {
    evidenceRef.current = evidenceHistory;
  }, [evidenceHistory]);
  useEffect(() => {
    mindmapsRef.current = mindmaps;
  }, [mindmaps]);
  useEffect(() => {
    titleRef.current = title;
  }, [title]);

  useEffect(() => {
    const current = conversationRef.current;
    if (!current || activeRef.current) return;
    const messageCount = current.messages.length;
    const nextEvidence = toMessageIndexed(
      current.evidence_history,
      messageCount,
      [],
    );
    const nextMindmaps = toMessageIndexed(
      current.mindmap_history,
      messageCount,
      null,
    );
    // Keep the refs in step with the state right away: `finally` persists them
    // into the cache and cannot wait for the post-render effect to run.
    messagesRef.current = current.messages;
    evidenceRef.current = nextEvidence;
    mindmapsRef.current = nextMindmaps;
    titleRef.current = null;
    setMessages(current.messages);
    setEvidenceHistory(nextEvidence);
    setMindmaps(nextMindmaps);
    setPhase("idle");
    setError(null);
    setSuggestions([]);
    setTitle(null);
    setWarning(null);
    setEvidenceView(null);
  }, [conversation?.id]);

  // Leaving the page must not leave the SSE request running: its callbacks keep
  // writing state, and `finally` would write an abandoned conversation into the
  // cache (mountedRef gates that write).
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      controllerRef.current?.abort();
    };
  }, []);

  const stop = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  const send = useCallback(
    async (text: string, options?: { regenerate?: boolean }) => {
      if (!conversationId || activeRef.current) return;

      const regenerate = options?.regenerate ?? false;
      const trimmed = text.trim();
      if (!regenerate && !trimmed) return;

      const source = messages;
      let userText = trimmed;
      let base = source;

      if (regenerate) {
        const lastUser = [...source].reverse().find((message) => message.role === "user");
        if (!lastUser) return;
        userText = lastUser.content;
        const lastAssistant = source.map((message) => message.role).lastIndexOf("assistant");
        if (lastAssistant === source.length - 1) base = source.slice(0, -1);
      }

      const next = regenerate
        ? base
        : [...base, { role: "user" as const, content: trimmed }];
      const assistantIndex = next.length;
      const body = buildBody(userText, regenerate);

      activeRef.current = true;
      setError(null);
      setSuggestions([]);
      setWarning(null);
      const nextMessages: ChatMessage[] = [...next, { role: "assistant", content: "" }];
      messagesRef.current = nextMessages;
      setMessages(nextMessages);
      setEvidenceHistory((current) => {
        const copy = regenerate ? current.slice(0, assistantIndex) : [...current];
        copy[assistantIndex] = [];
        evidenceRef.current = copy;
        return copy;
      });
      setMindmaps((current) => {
        const copy = regenerate ? current.slice(0, assistantIndex) : [...current];
        copy[assistantIndex] = null;
        mindmapsRef.current = copy;
        return copy;
      });
      setEvidenceView(null);
      setPhase("thinking");

      const controller = new AbortController();
      controllerRef.current = controller;

      const updateAssistant = (update: (message: ChatMessage) => ChatMessage) => {
        setMessages((current) => {
          const copy = [...current];
          const target = copy[assistantIndex];
          if (target) copy[assistantIndex] = update(target);
          // `finally` reads the ref; persisting from the updater keeps it from
          // lagging one render behind the last token.
          messagesRef.current = copy;
          return copy;
        });
      };

      try {
        await api.streamMessage(
          conversationId,
          body,
          {
            onStart: ({ warning: startWarning }) => {
              setPhase("streaming");
              if (startWarning) setWarning(startWarning);
            },
            onToken: ({ delta }) => {
              setPhase((current) => (current === "thinking" ? "streaming" : current));
              updateAssistant((message) => ({
                ...message,
                content: message.content + delta,
              }));
            },
            onReset: () => {
              updateAssistant((message) => ({ ...message, content: "" }));
            },
            onEvidence: ({ items }) => {
              setEvidenceHistory((current) => {
                const copy = [...current];
                copy[assistantIndex] = items;
                evidenceRef.current = copy;
                return copy;
              });
              setEvidenceView(assistantIndex);
            },
            onTitle: ({ name }) => {
              titleRef.current = name;
              setTitle(name);
              queryClient.setQueryData<ConversationDetail>(
                queryKeys.conversation(conversationId),
                (current) => (current ? { ...current, name } : current),
              );
            },
            onSuggestions: ({ items }) => setSuggestions(items),
            onMindmap: ({ markdown }) => {
              setMindmaps((current) => {
                const copy = [...current];
                copy[assistantIndex] = markdown;
                mindmapsRef.current = copy;
                return copy;
              });
            },
            onPlot: () => undefined,
            onDone: ({ name }) => {
              if (name) {
                titleRef.current = name;
                setTitle(name);
                queryClient.setQueryData<ConversationDetail>(
                  queryKeys.conversation(conversationId),
                  (current) => (current ? { ...current, name } : current),
                );
              }
              setPhase("idle");
              setEvidenceView(assistantIndex);
            },
            onError: ({ message }) => {
              setError(message);
              setPhase("error");
            },
          },
          controller.signal,
        );
      } catch (streamError) {
        if (isAbort(streamError)) {
          setPhase("idle");
          setMessages((current) => {
            const last = current[current.length - 1];
            if (last?.role === "assistant" && last.content.length === 0) {
              const cleaned = current.slice(0, -1);
              messagesRef.current = cleaned;
              return cleaned;
            }
            return current;
          });
        } else {
          const message =
            streamError instanceof ApiError
              ? streamError.message
              : streamError instanceof Error
                ? streamError.message
                : "stream failed";
          setError(message);
          setPhase("error");
        }
      } finally {
        activeRef.current = false;
        controllerRef.current = null;

        if (mountedRef.current) {
          queryClient.setQueryData<ConversationDetail>(
            queryKeys.conversation(conversationId),
            (current) =>
              current
                ? {
                    ...current,
                    name: titleRef.current ?? current.name,
                    messages: messagesRef.current,
                    // back to the server's per-pair shape for the cached payload
                    evidence_history: toPairIndexed(
                      evidenceRef.current,
                      messagesRef.current.length,
                      [],
                    ),
                    mindmap_history: toPairIndexed(
                      mindmapsRef.current,
                      messagesRef.current.length,
                      null,
                    ),
                  }
                : current,
          );
          void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
        }
      }
    },
    [buildBody, conversationId, messages, queryClient],
  );

  const isActive = phase === "thinking" || phase === "streaming";

  return {
    messages,
    evidenceHistory,
    mindmaps,
    phase,
    error,
    suggestions,
    title,
    warning,
    evidenceView,
    setEvidenceView,
    clearWarning: () => setWarning(null),
    isActive,
    send,
    stop,
  };
}
