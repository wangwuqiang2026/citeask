import { useQuery } from "@tanstack/react-query";
import { CircleAlert, ExternalLink, Keyboard } from "lucide-react";
import type { ReactNode } from "react";

import { PageFrame } from "@/components/app/PageFrame";
import { Markdown } from "@/components/chat/Markdown";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query";

function Card({
  title,
  children,
}: {
  title?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-md border border-border bg-panel p-5">
      {title ? (
        <h2 className="mb-3 text-sm font-medium text-fg">{title}</h2>
      ) : null}
      {children}
    </section>
  );
}

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <span className="text-sm text-muted">{label}</span>
      <span className="text-sm text-fg">{value}</span>
    </div>
  );
}

export function HelpPage() {
  const t = useT();

  const helpQuery = useQuery({
    queryKey: queryKeys.help,
    queryFn: () => api.getHelp(),
    staleTime: Infinity,
  });
  const help = helpQuery.data;

  return (
    <PageFrame
      title={t("help.title")}
      subtitle={
        help ? `${help.app.name} v${help.app.version}` : t("help.subtitle")
      }
    >
      {helpQuery.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : helpQuery.isError ? (
        <p className="flex items-center gap-2 text-sm text-danger" role="alert">
          <CircleAlert className="h-4 w-4" aria-hidden="true" />
          {t("help.loadError")}
        </p>
      ) : !help ? null : (
        <div className="space-y-4">
          <Card title={t("help.about")}>
            <InfoRow label={t("help.version")} value={help.app.version} />
            <InfoRow label={t("help.language")} value={help.app.language} />
            <InfoRow
              label={t("help.links")}
              value={
                <span className="inline-flex flex-wrap items-center gap-3">
                  <a
                    href="https://github.com/wangwuqiang2026/citeask"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-accent hover:underline"
                  >
                    {t("help.github")}
                    <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                  </a>
                  <a
                    href="/legacy/"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-accent hover:underline"
                  >
                    {t("help.classic")}
                    <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                  </a>
                </span>
              }
            />
            {help.about_md ? (
              <div className="mt-3 border-t border-border pt-3">
                <Markdown content={help.about_md} citationLabel="" />
              </div>
            ) : null}
          </Card>

          <Card title={t("help.userGuide")}>
            {help.usage_md ? (
              <Markdown content={help.usage_md} citationLabel="" />
            ) : (
              <p className="text-sm text-subtle">{t("help.empty")}</p>
            )}
          </Card>

          <Card title={t("help.shortcuts")}>
            <ul className="space-y-1.5 text-sm text-muted">
              <li className="flex items-center gap-2">
                <Keyboard className="h-4 w-4 text-subtle" aria-hidden="true" />
                {t("help.shortcutSend")}
              </li>
              <li className="flex items-center gap-2">
                <Keyboard className="h-4 w-4 text-subtle" aria-hidden="true" />
                {t("help.shortcutPalette")}
              </li>
            </ul>
          </Card>
        </div>
      )}
    </PageFrame>
  );
}
