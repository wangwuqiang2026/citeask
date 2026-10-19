import { FolderOpen, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";

interface EmptyChatProps {
  suggestions: string[];
  onSuggestion: (text: string) => void;
  onUpload: () => void;
  onChooseFiles: () => void;
}

/**
 * First-run state of a conversation: brand, one sentence, three suggested
 * questions and the two entry points (upload / pick files). Deliberately not a
 * card inside a card — it sits on the panel background.
 */
export function EmptyChat({
  suggestions,
  onSuggestion,
  onUpload,
  onChooseFiles,
}: EmptyChatProps) {
  const t = useT();

  return (
    <div className="mx-auto flex min-h-full w-full max-w-2xl flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-5 inline-flex h-12 w-12 items-center justify-center rounded-lg bg-accent text-2xl font-bold text-accent-fg">
        c
      </div>
      <h1 className="text-lg font-semibold text-fg">{t("chat.emptyTitle")}</h1>
      <p className="mt-2 max-w-md text-md leading-relaxed text-muted">
        {t("chat.emptyBody")}
      </p>

      <div className="mt-6 flex w-full flex-col gap-2">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onSuggestion(suggestion)}
            className="rounded-md border border-border bg-panel px-4 py-2.5 text-left text-sm text-fg transition-colors hover:border-accent/40 hover:bg-elevated"
          >
            {suggestion}
          </button>
        ))}
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        <Button variant="primary" onClick={onUpload}>
          <Upload className="h-4 w-4" aria-hidden="true" />
          {t("chat.upload")}
        </Button>
        <Button variant="secondary" onClick={onChooseFiles}>
          <FolderOpen className="h-4 w-4" aria-hidden="true" />
          {t("chat.chooseFiles")}
        </Button>
      </div>
    </div>
  );
}
