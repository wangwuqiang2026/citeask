import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Meta, SelectionMode } from "@/lib/types";

export interface ChatSettings {
  reasoning?: string;
  llm?: string;
  language?: string;
  citation?: string;
  /** null = follow `meta.features.mindmap` (capability ≠ default-on). */
  mindmap: boolean | null;
  selectionMode: SelectionMode;
}

interface ChatSettingsState extends ChatSettings {
  update: (patch: Partial<ChatSettings>) => void;
  /** Fill the still-undefined defaults from the backend metadata, once. */
  hydrate: (meta: Meta) => void;
}

const DEFAULTS: ChatSettings = { mindmap: null, selectionMode: "all" };

export const useChatSettings = create<ChatSettingsState>()(
  persist(
    (set) => ({
      ...DEFAULTS,
      update: (patch) => set(patch),
      hydrate: (meta) =>
        set((state) => ({
          reasoning: state.reasoning ?? meta.reasoning.default,
          llm: state.llm ?? "",
          language: state.language ?? meta.languages.default,
          citation: state.citation ?? meta.citations.default,
        })),
    }),
    {
      name: "citeask.chat",
      partialize: (state) => ({
        reasoning: state.reasoning,
        llm: state.llm,
        language: state.language,
        citation: state.citation,
        mindmap: state.mindmap,
        selectionMode: state.selectionMode,
      }),
    },
  ),
);
