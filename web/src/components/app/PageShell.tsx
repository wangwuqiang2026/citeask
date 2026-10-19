import { useT } from "@/lib/i18n";

export function PageShell({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const t = useT();
  return (
    <div className="flex min-h-0 flex-1 flex-col bg-canvas">
      <header className="flex h-14 shrink-0 items-center border-b border-border bg-panel px-5">
        <h1 className="truncate text-md font-semibold text-fg">{title}</h1>
      </header>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-5 py-8">
          {children}
          <p className="mt-6 text-xs text-subtle">
            {t("app.name")} · {t("classic.note")}
          </p>
        </div>
      </div>
    </div>
  );
}
