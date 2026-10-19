import {
  ArrowUpRight,
  FolderOpen,
  HelpCircle,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";

import { PageShell } from "@/components/app/PageShell";
import { useT, type MessageKey } from "@/lib/i18n";

type ClassicKind = "files" | "settings" | "resources" | "help";

const ICONS = {
  files: FolderOpen,
  settings: SlidersHorizontal,
  resources: Sparkles,
  help: HelpCircle,
} as const;

export function ClassicPage({
  kind,
  titleKey,
  bodyKey,
}: {
  kind: ClassicKind;
  titleKey: MessageKey;
  bodyKey: MessageKey;
}) {
  const t = useT();
  const Icon = ICONS[kind];

  return (
    <PageShell title={t(titleKey)}>
      <section className="rounded-lg border border-border bg-panel p-6">
        <div className="flex items-start gap-3">
          <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-elevated text-muted">
            <Icon className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-md font-semibold text-fg">{t(titleKey)}</h2>
            <p className="mt-1 max-w-prose text-sm leading-relaxed text-muted">
              {t(bodyKey)}
            </p>
            <a
              href="/legacy"
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
            >
              {t("classic.open")}
              <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
            </a>
          </div>
        </div>
      </section>
    </PageShell>
  );
}
