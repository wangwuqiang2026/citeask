import {
  ArrowUp,
  AtSign,
  BrainCircuit,
  Languages,
  Loader2,
  Paperclip,
  Quote,
  SlidersHorizontal,
  Sparkles,
  Square,
  Upload,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { FileOption } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn, shouldSubmitOnEnter } from "@/lib/utils";

const MENTION_PATTERN = /@(?:"([^"]+)"|(\S+))/g;

function parseMentions(value: string): { webSearch: boolean; files: string[] } {
  const files: string[] = [];
  let webSearch = false;
  for (const match of value.matchAll(MENTION_PATTERN)) {
    const mention = match[1] ?? match[2] ?? "";
    if (mention.toLowerCase() === "websearch") webSearch = true;
    else if (mention) files.push(mention);
  }
  return { webSearch, files };
}

interface ComposerProps {
  onSend: (text: string) => void;
  streaming: boolean;
  onStop: () => void;
  disabled?: boolean;
  pendingFiles: FileOption[];
  onRemoveFile: (id: string) => void;
  onOpenFilePicker: () => void;
  onUploadLegacy: () => void;
  onOpenSettings: () => void;
  reasoningLabel: string;
  modelLabel: string;
  languageLabel: string;
  citationLabel: string;
  scopeLabel: string;
  mindmapOn: boolean;
}

function Pill({
  icon,
  label,
  onClick,
  title,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  title: string;
}) {
  if (!label) return null;
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className="inline-flex items-center gap-1 rounded-full border border-border bg-panel px-2 py-0.5 text-2xs text-muted transition-colors hover:border-accent/40 hover:text-fg"
    >
      {icon}
      <span className="max-w-[110px] truncate">{label}</span>
    </button>
  );
}

export function Composer({
  onSend,
  streaming,
  onStop,
  disabled = false,
  pendingFiles,
  onRemoveFile,
  onOpenFilePicker,
  onUploadLegacy,
  onOpenSettings,
  reasoningLabel,
  modelLabel,
  languageLabel,
  citationLabel,
  scopeLabel,
  mindmapOn,
}: ComposerProps) {
  const t = useT();
  const [value, setValue] = useState("");
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const mentions = parseMentions(value);
  const canSend = value.trim().length > 0 && !streaming && !disabled;

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    // An empty composer keeps the single-row height from the markup; measuring at
    // that moment returned a stretched value and left the box at the 200px cap.
    if (!value) {
      element.style.height = "";
      return;
    }
    element.style.height = "0px";
    element.style.height = `${Math.min(element.scrollHeight, 200)}px`;
  }, [value]);

  const submit = () => {
    if (!canSend) return;
    onSend(value.trim());
    setValue("");
  };

  const focusInput = () => {
    textareaRef.current?.focus();
  };

  const insertMention = () => {
    setValue((current) => (current.endsWith(" ") || current === "" ? `${current}@` : `${current} @`));
    focusInput();
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // An IME uses Enter to confirm a candidate; sending would swallow the word.
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;
    if (!shouldSubmitOnEnter(event)) return;
    event.preventDefault();
    submit();
  };

  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    if (event.dataTransfer.files.length > 0) onUploadLegacy();
  };

  return (
    <div className="shrink-0 px-3 pb-3 pt-1 md:px-6 md:pb-5">
      <div className="mx-auto w-full max-w-3xl">
        <div
          className={cn(
            "relative rounded-lg border border-border bg-panel shadow-composer transition-colors",
            "focus-within:border-accent/50",
            dragging && "border-accent",
          )}
          onDragEnter={(event) => {
            event.preventDefault();
            dragDepth.current += 1;
            if (event.dataTransfer.types.includes("Files")) setDragging(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            event.preventDefault();
            dragDepth.current = Math.max(0, dragDepth.current - 1);
            if (dragDepth.current === 0) setDragging(false);
          }}
          onDrop={onDrop}
        >
          {dragging ? (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-accent bg-accent-soft/90 text-center">
              <Upload className="h-5 w-5 text-accent" aria-hidden="true" />
              <p className="text-sm font-medium text-fg">{t("chat.dragTitle")}</p>
              <p className="text-xs text-muted">{t("chat.dragBody")}</p>
            </div>
          ) : null}

          {pendingFiles.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 border-b border-border px-3 py-2">
              {pendingFiles.map((file) => (
                <span
                  key={file.id}
                  className="inline-flex max-w-[220px] items-center gap-1 rounded-full bg-elevated px-2 py-0.5 text-2xs text-fg"
                >
                  <span className="truncate" title={file.file_name}>
                    {file.file_name}
                  </span>
                  <button
                    type="button"
                    aria-label={t("chat.attachments")}
                    onClick={() => onRemoveFile(file.id)}
                    className="text-subtle hover:text-fg"
                  >
                    <X className="h-3 w-3" aria-hidden="true" />
                  </button>
                </span>
              ))}
            </div>
          ) : null}

          {mentions.webSearch || mentions.files.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 px-3 pt-2">
              {mentions.webSearch ? (
                <Badge variant="accent">
                  <Sparkles className="h-3 w-3" aria-hidden="true" />
                  WebSearch
                </Badge>
              ) : null}
              {mentions.files.map((name) => (
                <Badge key={name} variant="outline">
                  @{name}
                </Badge>
              ))}
            </div>
          ) : null}

          <textarea
            ref={textareaRef}
            value={value}
            rows={1}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder={t("chat.composerPlaceholder")}
            aria-label={t("chat.composerPlaceholder")}
            disabled={disabled}
            className="max-h-[200px] w-full resize-none bg-transparent px-3.5 pb-1 pt-3 text-md leading-relaxed text-fg outline-none placeholder:text-subtle disabled:opacity-60"
          />

          <div className="flex items-center gap-1 px-2 pb-2 pt-1">
            <DropdownMenu>
              <Tooltip>
                <TooltipTrigger asChild>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={t("chat.attachments")}
                    >
                      <Paperclip className="h-4 w-4" aria-hidden="true" />
                    </Button>
                  </DropdownMenuTrigger>
                </TooltipTrigger>
                <TooltipContent>{t("chat.attachments")}</TooltipContent>
              </Tooltip>
              <DropdownMenuContent side="top" align="start">
                <DropdownMenuItem onSelect={onOpenFilePicker}>
                  <Paperclip className="h-4 w-4" aria-hidden="true" />
                  {t("chat.chooseFiles")}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={onUploadLegacy}>
                  <Upload className="h-4 w-4" aria-hidden="true" />
                  {t("chat.upload")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="@"
                  onClick={insertMention}
                >
                  <AtSign className="h-4 w-4" aria-hidden="true" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>@WebSearch / @file</TooltipContent>
            </Tooltip>

            <div className="mx-1 hidden h-4 w-px bg-border sm:block" />

            <div className="no-scrollbar flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
              <Pill
                icon={<SlidersHorizontal className="h-3 w-3" aria-hidden="true" />}
                label={scopeLabel}
                onClick={onOpenSettings}
                title={t("settings.scope")}
              />
              <Pill
                icon={<BrainCircuit className="h-3 w-3" aria-hidden="true" />}
                label={reasoningLabel}
                onClick={onOpenSettings}
                title={t("settings.reasoning")}
              />
              <Pill
                icon={<Sparkles className="h-3 w-3" aria-hidden="true" />}
                label={modelLabel}
                onClick={onOpenSettings}
                title={t("settings.model")}
              />
              <Pill
                icon={<Languages className="h-3 w-3" aria-hidden="true" />}
                label={languageLabel}
                onClick={onOpenSettings}
                title={t("settings.language")}
              />
              <Pill
                icon={<Quote className="h-3 w-3" aria-hidden="true" />}
                label={citationLabel}
                onClick={onOpenSettings}
                title={t("settings.citation")}
              />
              {mindmapOn ? (
                <Badge variant="outline" className="hidden sm:inline-flex">
                  {t("settings.mindmap")}
                </Badge>
              ) : null}
            </div>

            {streaming ? (
              <Button
                variant="danger"
                size="icon"
                aria-label={t("chat.stop")}
                onClick={onStop}
                className="shrink-0 rounded-full"
              >
                <Square className="h-3.5 w-3.5" aria-hidden="true" />
              </Button>
            ) : (
              <Button
                variant="primary"
                size="icon"
                aria-label={t("chat.send")}
                disabled={!canSend}
                onClick={submit}
                className="shrink-0 rounded-full"
              >
                {disabled ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <ArrowUp className="h-4 w-4" aria-hidden="true" />
                )}
              </Button>
            )}
          </div>
        </div>

        <p className="mt-1.5 px-1 text-2xs text-subtle">{t("chat.composerHint")}</p>
      </div>
    </div>
  );
}
