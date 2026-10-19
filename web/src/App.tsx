import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Toaster } from "sonner";

import { AppShell } from "@/components/app/AppShell";
import { Button } from "@/components/ui/button";
import { useMe, useMeta } from "@/hooks/use-api";
import { useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query";
import { applyTheme, watchSystemTheme } from "@/lib/theme";
import { ChatPage } from "@/pages/ChatPage";
import { ClassicPage } from "@/pages/ClassicPage";
import { FilesPage } from "@/pages/FilesPage";
import { LoginPage } from "@/pages/LoginPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { useUiStore } from "@/stores/ui";

function BootScreen() {
  const t = useT();
  return (
    <div className="flex h-dvh items-center justify-center bg-canvas">
      <div className="flex flex-col items-center gap-3">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-md bg-accent text-lg font-bold text-accent-fg">
          c
        </span>
        <span className="text-sm text-muted" role="status">
          {t("common.loading")}
        </span>
      </div>
    </div>
  );
}

/**
 * `/api/v1/meta` carries the labels, indices and feature flags the shell needs.
 * It is authenticated, so it can fail while the session is still valid (server
 * restart, expired token race). Offer a retry instead of an endless spinner.
 */
function MetaErrorScreen({ onRetry }: { onRetry: () => void }) {
  const t = useT();
  return (
    <div className="flex h-dvh items-center justify-center bg-canvas px-6">
      <div className="w-full max-w-[420px] rounded-lg border border-border bg-panel p-6 text-center shadow-composer">
        <h1 className="text-sm font-semibold text-fg">{t("error.metaTitle")}</h1>
        <p className="mt-2 text-sm text-muted">{t("error.metaBody")}</p>
        <Button type="button" variant="primary" className="mt-4" onClick={onRetry}>
          {t("common.retry")}
        </Button>
      </div>
    </div>
  );
}

function Protected({
  requireLogin,
  signedIn,
}: {
  requireLogin: boolean;
  signedIn: boolean;
}) {
  if (requireLogin && !signedIn) return <Navigate to="/login" replace />;
  return <AppShell />;
}

export function App() {
  const t = useT();
  const queryClient = useQueryClient();
  const theme = useUiStore((state) => state.theme);
  const lang = useUiStore((state) => state.lang);
  const setLang = useUiStore((state) => state.setLang);

  const meQuery = useMe();
  const user = meQuery.data?.user ?? null;
  // `/api/v1/meta` requires a session; requesting it anonymously is a guaranteed
  // 401 and used to loop the boot screen forever (MODIFICATIONS §5.26).
  const metaQuery = useMeta(user !== null);
  const meta = metaQuery.data;
  const requireLogin = meta?.features.user_management ?? true;

  useEffect(() => {
    applyTheme(theme);
    return watchSystemTheme(theme, () => applyTheme(theme));
  }, [theme]);

  useEffect(() => {
    if (lang === null && meta?.app.language) {
      setLang(meta.app.language === "en" ? "en" : "zh");
    }
  }, [lang, meta?.app.language, setLang]);

  useEffect(() => {
    document.documentElement.lang = (lang ?? "zh") === "en" ? "en" : "zh-CN";
  }, [lang]);

  useEffect(() => {
    const onUnauthorized = () => {
      queryClient.setQueryData(queryKeys.me, { user: null });
      // The cached metadata belongs to the session that just expired.
      queryClient.removeQueries({ queryKey: queryKeys.meta, exact: true });
    };
    window.addEventListener("citeask:unauthorized", onUnauthorized);
    return () => window.removeEventListener("citeask:unauthorized", onUnauthorized);
  }, [queryClient]);

  if (meQuery.isLoading) {
    return <BootScreen />;
  }

  if (user !== null && metaQuery.isLoading) {
    return <BootScreen />;
  }

  if (user !== null && meta === undefined && metaQuery.isError) {
    return <MetaErrorScreen onRetry={() => void metaQuery.refetch()} />;
  }

  return (
    <>
      <Routes>
        <Route
          path="/login"
          element={requireLogin ? <LoginPage /> : <Navigate to="/chat" replace />}
        />

        <Route
          element={<Protected requireLogin={requireLogin} signedIn={user !== null} />}
        >
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chat/:id" element={<ChatPage />} />
          <Route path="/files" element={<FilesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route
            path="/resources"
            element={
              <ClassicPage
                kind="resources"
                titleKey="classic.resourcesTitle"
                bodyKey="classic.resourcesBody"
              />
            }
          />
          <Route
            path="/help"
            element={
              <ClassicPage
                kind="help"
                titleKey="classic.helpTitle"
                bodyKey="classic.helpBody"
              />
            }
          />
          <Route path="/login" element={<Navigate to="/chat" replace />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Route>
      </Routes>

      <Toaster position="top-center" theme={theme} richColors closeButton />
      <span className="sr-only" role="status">
        {t("app.name")}
      </span>
    </>
  );
}
