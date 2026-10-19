import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useMe } from "@/hooks/use-api";
import { ApiError, api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query";

export function LoginPage() {
  const t = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: me } = useMe();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useMutation({
    mutationFn: () => api.login(username.trim(), password),
    onSuccess: ({ user }) => {
      api.rememberLegacyCredentials(username.trim(), password);
      queryClient.setQueryData(queryKeys.me, { user });
      void queryClient.invalidateQueries();
      navigate("/chat", { replace: true });
    },
    onError: (mutationError) => {
      setError(
        mutationError instanceof ApiError && mutationError.status === 401
          ? t("login.invalid")
          : t("error.generic"),
      );
    },
  });

  // No metadata lookup here: `/api/v1/meta` needs a session. When the instance
  // has user management disabled, `/auth/me` already returns the anonymous user
  // and the redirect below sends the visitor straight to the chat.
  if (me?.user) {
    return <Navigate to="/chat" replace />;
  }

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!username.trim() || !password) {
      setError(t("login.required"));
      return;
    }
    login.mutate();
  };

  return (
    <div className="flex min-h-dvh flex-1 items-center justify-center bg-canvas px-6 py-10">
      <div className="w-full max-w-[400px]">
        <div className="mb-6 flex items-center gap-3">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-md bg-accent text-lg font-bold text-accent-fg">
            c
          </span>
          <div>
            <h1 className="text-lg font-semibold text-fg">{t("login.title")}</h1>
            <p className="text-sm text-muted">{t("login.subtitle")}</p>
          </div>
        </div>

        <form
          onSubmit={submit}
          className="space-y-4 rounded-lg border border-border bg-panel p-6 shadow-composer"
        >
          <div className="space-y-1.5">
            <label htmlFor="login-username" className="block text-sm text-fg">
              {t("login.username")}
            </label>
            <Input
              id="login-username"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              aria-invalid={error !== null}
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="login-password" className="block text-sm text-fg">
              {t("login.password")}
            </label>
            <div className="relative">
              <Input
                id="login-password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="pr-10"
                aria-invalid={error !== null}
              />
              <button
                type="button"
                onClick={() => setShowPassword((current) => !current)}
                aria-label={showPassword ? t("login.hidePassword") : t("login.showPassword")}
                className="absolute right-1 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-sm text-subtle transition-colors hover:bg-elevated hover:text-fg"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Eye className="h-4 w-4" aria-hidden="true" />
                )}
              </button>
            </div>
          </div>

          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}

          <Button
            type="submit"
            variant="primary"
            className="w-full"
            disabled={login.isPending}
          >
            {login.isPending ? t("login.submitting") : t("login.submit")}
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-subtle">
          <a href="/legacy" className="hover:text-fg hover:underline">
            {t("rail.legacy")}
          </a>
        </p>
      </div>
    </div>
  );
}
