import { useMutation } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useMeta } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";

/**
 * `POST /api/v1/auth/password`: the signed-in user changes their own password.
 * The rules live on the server; this form only checks the two entries match so a
 * typo is caught before the request.
 */
export function AccountCard() {
  const t = useT();
  const { data: meta } = useMeta();
  const user = meta?.user ?? null;

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);

  const change = useMutation({
    mutationFn: () => api.changePassword(current, next),
    onSuccess: () => {
      setCurrent("");
      setNext("");
      setConfirm("");
      setError(null);
      toast.success(t("account.changed"));
    },
    onError: (mutationError: Error) => {
      setError(mutationError.message || t("account.changeFailed"));
    },
  });

  const submit = () => {
    if (!current || !next || !confirm) {
      setError(t("account.required"));
      return;
    }
    if (next !== confirm) {
      setError(t("account.mismatch"));
      return;
    }
    setError(null);
    change.mutate();
  };

  return (
    <section className="rounded-md border border-border bg-panel p-5">
      <header className="mb-4 flex items-center gap-2">
        <KeyRound className="h-4 w-4 text-accent" aria-hidden="true" />
        <div>
          <h2 className="text-sm font-medium text-fg">{t("account.title")}</h2>
          <p className="text-2xs text-subtle">
            {t("account.subtitle")}
            {user ? ` (${user.username})` : ""}
          </p>
        </div>
      </header>

      <div className="grid max-w-2xl gap-3 sm:grid-cols-3">
        <label className="block space-y-1">
          <span className="text-xs text-muted">{t("account.currentPassword")}</span>
          <Input
            type="password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            autoComplete="current-password"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-xs text-muted">{t("account.newPassword")}</span>
          <Input
            type="password"
            value={next}
            onChange={(event) => setNext(event.target.value)}
            autoComplete="new-password"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-xs text-muted">{t("account.confirmPassword")}</span>
          <Input
            type="password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            autoComplete="new-password"
          />
        </label>
      </div>

      {error ? (
        <p role="alert" className="mt-3 text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="mt-4">
        <Button
          variant="secondary"
          onClick={submit}
          disabled={change.isPending || !user}
        >
          {change.isPending ? t("account.changing") : t("account.change")}
        </Button>
      </div>
    </section>
  );
}
