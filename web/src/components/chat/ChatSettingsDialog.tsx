import { useEffect } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useMeta } from "@/hooks/use-api";
import { useT } from "@/lib/i18n";
import type { Choice, SelectionMode } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useChatSettings } from "@/stores/chat-settings";

interface ChatSettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function Field({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5">
      <label htmlFor={id} className="text-sm text-fg">
        {label}
      </label>
      <div className="w-52 shrink-0">{children}</div>
    </div>
  );
}

function ChoiceSelect({
  id,
  value,
  choices,
  onChange,
}: {
  id: string;
  value: string | undefined;
  choices: Choice[];
  onChange: (value: string) => void;
}) {
  return (
    <Select value={value ?? ""} onValueChange={onChange}>
      <SelectTrigger id={id} aria-label={id}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {choices.map((choice) => (
          <SelectItem key={choice.value} value={choice.value}>
            {choice.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function ChatSettingsDialog({ open, onOpenChange }: ChatSettingsDialogProps) {
  const t = useT();
  const { data: meta } = useMeta();
  const settings = useChatSettings();
  const update = useChatSettings((state) => state.update);

  useEffect(() => {
    if (meta) useChatSettings.getState().hydrate(meta);
  }, [meta]);

  if (!meta) return null;

  const mindmapOn = settings.mindmap ?? meta.features.mindmap;
  const scopeOptions: { value: SelectionMode; label: string }[] = [
    { value: "all", label: t("settings.scopeAll") },
    { value: "select", label: t("settings.scopeSelect") },
    { value: "disabled", label: t("settings.scopeDisabled") },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("settings.title")}</DialogTitle>
          <DialogDescription>{t("settings.note")}</DialogDescription>
        </DialogHeader>

        <div className="divide-y divide-border">
          <Field id="setting-reasoning" label={t("settings.reasoning")}>
            <ChoiceSelect
              id="setting-reasoning"
              value={settings.reasoning}
              choices={meta.reasoning.choices}
              onChange={(reasoning) => update({ reasoning })}
            />
          </Field>

          {meta.models.choices.length > 0 ? (
            <Field id="setting-model" label={t("settings.model")}>
              <ChoiceSelect
                id="setting-model"
                value={settings.llm}
                choices={meta.models.choices}
                onChange={(llm) => update({ llm })}
              />
            </Field>
          ) : null}

          <Field id="setting-language" label={t("settings.language")}>
            <ChoiceSelect
              id="setting-language"
              value={settings.language}
              choices={meta.languages.choices}
              onChange={(language) => update({ language })}
            />
          </Field>

          <Field id="setting-citation" label={t("settings.citation")}>
            <ChoiceSelect
              id="setting-citation"
              value={settings.citation}
              choices={meta.citations.choices}
              onChange={(citation) => update({ citation })}
            />
          </Field>

          {meta.features.mindmap ? (
            <div className="flex items-center justify-between gap-4 py-2.5">
              <label htmlFor="setting-mindmap" className="text-sm text-fg">
                {t("settings.mindmap")}
              </label>
              <Switch
                id="setting-mindmap"
                checked={mindmapOn}
                onCheckedChange={(mindmap) => update({ mindmap })}
              />
            </div>
          ) : null}

          <div className="py-3">
            <p className="mb-2 text-sm text-fg">{t("settings.scope")}</p>
            <div
              role="radiogroup"
              aria-label={t("settings.scope")}
              className="flex gap-1 rounded-md border border-border p-1"
            >
              {scopeOptions.map((option) => {
                const active = settings.selectionMode === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => update({ selectionMode: option.value })}
                    className={cn(
                      "flex-1 rounded-sm px-2 py-1.5 text-xs transition-colors",
                      active
                        ? "bg-accent text-accent-fg"
                        : "text-muted hover:bg-elevated hover:text-fg",
                    )}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
            {settings.selectionMode === "select" ? (
              <p className="mt-2 text-xs text-subtle">{t("chat.uploadSoon")}</p>
            ) : null}
          </div>
        </div>

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="inline-flex h-9 items-center rounded-sm bg-accent px-4 text-sm font-medium text-accent-fg hover:bg-accent-hover"
          >
            {t("settings.done")}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
