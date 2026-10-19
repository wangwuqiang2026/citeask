import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemeMode = "light" | "dark" | "system";
export type Lang = "zh" | "en";

interface UiState {
  theme: ThemeMode;
  /** null = follow the backend language from `/api/v1/meta`. */
  lang: Lang | null;
  sidebarOpen: boolean;
  evidenceOpen: boolean;
  commandOpen: boolean;
  settingsOpen: boolean;
  setTheme: (theme: ThemeMode) => void;
  setLang: (lang: Lang | null) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setEvidenceOpen: (open: boolean) => void;
  setCommandOpen: (open: boolean) => void;
  setSettingsOpen: (open: boolean) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      theme: "system",
      lang: null,
      sidebarOpen: true,
      // The evidence pane opens itself once an answer arrives with sources, so a
      // fresh conversation starts with the full width available.
      evidenceOpen: false,
      commandOpen: false,
      settingsOpen: false,
      setTheme: (theme) => set({ theme }),
      setLang: (lang) => set({ lang }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
      setEvidenceOpen: (evidenceOpen) => set({ evidenceOpen }),
      setCommandOpen: (commandOpen) => set({ commandOpen }),
      setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
    }),
    {
      name: "citeask.ui",
      partialize: (state) => ({
        theme: state.theme,
        lang: state.lang,
        sidebarOpen: state.sidebarOpen,
        evidenceOpen: state.evidenceOpen,
      }),
    },
  ),
);
