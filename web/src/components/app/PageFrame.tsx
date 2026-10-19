import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface PageFrameProps {
  title: string;
  subtitle?: string;
  /** Buttons rendered on the right of the header. */
  actions?: ReactNode;
  /** Sticky bar rendered below the scroll area (save bars, hints). */
  footer?: ReactNode;
  /** Wide pages (tables, forms with a side nav) opt out of the reading width. */
  wide?: boolean;
  children: ReactNode;
}

/**
 * Standard page chrome for the non-chat pages: a header that matches the chat
 * page, one scroll container, and an optional sticky footer. Keeping this in one
 * place is what makes /files and /settings feel like the same application.
 */
export function PageFrame({
  title,
  subtitle,
  actions,
  footer,
  wide = false,
  children,
}: PageFrameProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col bg-canvas">
      <header className="flex min-h-14 shrink-0 items-center gap-3 border-b border-border bg-panel px-5 py-2">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-md font-semibold text-fg">{title}</h1>
          {subtitle ? (
            <p className="truncate text-2xs text-subtle">{subtitle}</p>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </header>

      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        <div
          className={cn(
            "mx-auto w-full px-5 py-6",
            wide ? "max-w-[1400px]" : "max-w-3xl",
          )}
        >
          {children}
        </div>
      </div>

      {footer}
    </div>
  );
}
