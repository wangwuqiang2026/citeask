import { useEffect } from "react";
import { Outlet } from "react-router-dom";

import { CommandPalette } from "@/components/app/CommandPalette";
import { Rail } from "@/components/app/Rail";
import { ChatSettingsDialog } from "@/components/chat/ChatSettingsDialog";
import { useT } from "@/lib/i18n";
import { useUiStore } from "@/stores/ui";

export function AppShell() {
  const t = useT();
  const setCommandOpen = useUiStore((state) => state.setCommandOpen);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(!useUiStore.getState().commandOpen);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [setCommandOpen]);

  return (
    <div className="flex h-dvh overflow-hidden bg-canvas">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-sm focus:bg-panel focus:px-3 focus:py-2 focus:text-sm focus:shadow-pop"
      >
        {t("a11y.skip")}
      </a>
      <Rail />
      <div id="main-content" className="flex min-w-0 flex-1 overflow-hidden">
        <Outlet />
      </div>
      <CommandPalette />
      <ChatSettingsDialog
        open={useUiStore((state) => state.settingsOpen)}
        onOpenChange={useUiStore((state) => state.setSettingsOpen)}
      />
    </div>
  );
}
