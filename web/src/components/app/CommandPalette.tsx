import { Command } from "cmdk";
import { MessagesSquare, Moon, Plus, Search, Settings2, Sun, Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useConversations, useCreateConversation } from "@/hooks/use-api";
import { useT } from "@/lib/i18n";
import { useUiStore } from "@/stores/ui";

const itemClass =
  "flex cursor-pointer items-center gap-2 rounded-sm px-2 py-2 text-sm text-fg outline-none data-[selected=true]:bg-elevated";

const groupClass =
  "px-1 py-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-subtle";

export function CommandPalette() {
  const t = useT();
  const navigate = useNavigate();
  const open = useUiStore((state) => state.commandOpen);
  const setOpen = useUiStore((state) => state.setCommandOpen);
  const setSettingsOpen = useUiStore((state) => state.setSettingsOpen);
  const setTheme = useUiStore((state) => state.setTheme);
  const theme = useUiStore((state) => state.theme);
  const { data: conversations } = useConversations(open);
  const createConversation = useCreateConversation();

  const isDark =
    theme === "dark" ||
    (theme === "system" &&
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);

  const run = (action: () => void | Promise<void>) => {
    setOpen(false);
    void action();
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-xl gap-0 overflow-hidden p-0" hideClose>
        <DialogTitle className="sr-only">{t("command.title")}</DialogTitle>
        <Command
          label={t("command.title")}
          loop
          className="[&_[cmdk-input-wrapper]]:flex [&_[cmdk-input-wrapper]]:items-center [&_[cmdk-input-wrapper]]:gap-2 [&_[cmdk-input-wrapper]]:border-b [&_[cmdk-input-wrapper]]:border-border [&_[cmdk-input-wrapper]]:px-3"
        >
          <div className="flex items-center gap-2 px-3">
            <Search className="h-4 w-4 text-subtle" aria-hidden="true" />
            <Command.Input
              autoFocus
              placeholder={t("command.placeholder")}
              className="h-11 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-subtle"
            />
            <kbd className="rounded-sm border border-border px-1.5 py-0.5 font-mono text-2xs text-subtle">
              esc
            </kbd>
          </div>

          <Command.List className="max-h-[360px] overflow-y-auto p-1.5">
            <Command.Empty className="px-3 py-8 text-center text-sm text-muted">
              {t("command.noResults")}
            </Command.Empty>

            <Command.Group heading={t("command.title")} className={groupClass}>
              <Command.Item
                className={itemClass}
                onSelect={() =>
                  run(async () => {
                    const summary = await createConversation.mutateAsync();
                    toast.success(t("toast.created"));
                    navigate(`/chat/${summary.id}`);
                  })
                }
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                {t("command.newChat")}
              </Command.Item>
              <Command.Item
                className={itemClass}
                onSelect={() => run(() => setSettingsOpen(true))}
              >
                <Settings2 className="h-4 w-4" aria-hidden="true" />
                {t("command.openSettings")}
              </Command.Item>
              <Command.Item
                className={itemClass}
                onSelect={() => run(() => setTheme(isDark ? "light" : "dark"))}
              >
                {isDark ? (
                  <Sun className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Moon className="h-4 w-4" aria-hidden="true" />
                )}
                {t("command.toggleTheme")}
              </Command.Item>
              <Command.Item
                className={itemClass}
                onSelect={() =>
                  run(() => {
                    window.open("/legacy", "_blank");
                  })
                }
              >
                <Upload className="h-4 w-4" aria-hidden="true" />
                {t("command.upload")}
              </Command.Item>
            </Command.Group>

            {conversations && conversations.items.length > 0 ? (
              <Command.Group heading={t("nav.chat")} className={groupClass}>
                {conversations.items.slice(0, 12).map((conversation) => (
                  <Command.Item
                    key={conversation.id}
                    value={`${conversation.name} ${conversation.id}`}
                    className={itemClass}
                    onSelect={() =>
                      run(() => navigate(`/chat/${conversation.id}`))
                    }
                  >
                    <MessagesSquare className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span className="truncate">{conversation.name}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
