import { useMutation, useQuery } from "@tanstack/react-query";
import { CircleAlert, Loader2, RotateCcw, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { PageFrame } from "@/components/app/PageFrame";
import { SettingsField } from "@/components/settings/SettingsField";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query";
import { changedSettings, mergeSettings, settingKeys } from "@/lib/settings";
import type { SettingsSchema } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * `/settings`: a schema-driven form. The server describes every field (label,
 * control, choices, default), the form edits a flat `key -> value` map and the
 * save only sends the keys that changed, so a second tab is not overwritten.
 */
export function SettingsPage() {
  const t = useT();

  const schemaQuery = useQuery({
    queryKey: queryKeys.settingsSchema,
    queryFn: () => api.getSettingsSchema(),
    staleTime: Infinity,
  });
  const valuesQuery = useQuery({
    queryKey: queryKeys.settings,
    queryFn: () => api.getSettings(),
    staleTime: Infinity,
  });

  const [values, setValues] = useState<Record<string, unknown>>({});
  const [initial, setInitial] = useState<Record<string, unknown>>({});
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);
  const [invalidKeys, setInvalidKeys] = useState<Record<string, boolean>>({});
  const [resetToken, setResetToken] = useState(0);
  const [saveError, setSaveError] = useState<string | null>(null);

  const schema = schemaQuery.data;
  const groups = schema?.groups ?? [];

  useEffect(() => {
    if (!schema || !valuesQuery.data) return;
    const merged = mergeSettings(schema, valuesQuery.data.values);
    setValues(merged);
    setInitial(merged);
    setActiveGroupId((current) =>
      current && groups.some((group) => group.id === current)
        ? current
        : (groups[0]?.id ?? null),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schema, valuesQuery.data]);

  const keys = useMemo(() => settingKeys(schema), [schema]);
  const changed = useMemo(
    () => changedSettings(initial, values, keys),
    [initial, values, keys],
  );
  const dirty = Object.keys(changed).length > 0;
  const hasInvalid = Object.values(invalidKeys).some(Boolean);
  const activeGroup =
    groups.find((group) => group.id === activeGroupId) ?? groups[0];

  const save = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.putSettings(payload),
    onSuccess: (data) => {
      const next = mergeSettings(schema as SettingsSchema, data.values);
      setValues(next);
      setInitial(next);
      setInvalidKeys({});
      setSaveError(null);
      toast.success(t("settingsPage.saved"));
    },
    onError: (error: Error) => {
      setSaveError(error.message || t("settingsPage.saveFailed"));
      toast.error(error.message || t("settingsPage.saveFailed"));
    },
  });

  const update = (key: string, value: unknown) => {
    setValues((current) => ({ ...current, [key]: value }));
    setSaveError(null);
  };

  const markValidity = (key: string, valid: boolean) => {
    setInvalidKeys((current) => {
      if (Boolean(current[key]) === !valid) return current;
      return { ...current, [key]: !valid };
    });
  };

  const discard = () => {
    setValues(initial);
    setInvalidKeys({});
    setSaveError(null);
    setResetToken((token) => token + 1);
    toast.info(t("settingsPage.discard"));
  };

  const submit = () => {
    if (hasInvalid) {
      toast.error(t("settingsPage.numberInvalid"));
      return;
    }
    if (!dirty) {
      toast.info(t("settingsPage.saved"));
      return;
    }
    save.mutate(changed);
  };

  const loading = schemaQuery.isLoading || valuesQuery.isLoading;
  const failed = schemaQuery.isError || valuesQuery.isError;

  return (
    <PageFrame
      wide
      title={t("settingsPage.title")}
      subtitle={t("settingsPage.subtitle")}
      footer={
        <div className="flex items-center gap-3 border-t border-border bg-panel px-5 py-2.5">
          <span
            className={cn(
              "text-xs",
              dirty ? "text-warning" : "text-subtle",
            )}
            role="status"
          >
            {dirty ? t("settingsPage.unsaved") : null}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={discard}
              disabled={!dirty || save.isPending}
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              {t("settingsPage.discard")}
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={submit}
              disabled={!dirty || hasInvalid || save.isPending}
            >
              {save.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Save className="h-4 w-4" aria-hidden="true" />
              )}
              {save.isPending ? t("settingsPage.saving") : t("settingsPage.save")}
            </Button>
          </div>
        </div>
      }
    >
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-14 w-full" />
          ))}
        </div>
      ) : failed ? (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger"
        >
          <CircleAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="flex-1">{t("settingsPage.loadError")}</span>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              void schemaQuery.refetch();
              void valuesQuery.refetch();
            }}
          >
            {t("common.retry")}
          </Button>
        </div>
      ) : groups.length === 0 ? (
        <p className="rounded-md border border-dashed border-border bg-panel px-4 py-10 text-center text-sm text-muted">
          {t("settingsPage.empty")}
        </p>
      ) : (
        <div className="flex flex-col gap-6 lg:flex-row">
          <nav
            aria-label={t("settingsPage.title")}
            className="shrink-0 lg:w-56"
          >
            <div className="flex gap-1 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
              {groups.map((group) => {
                const active = group.id === activeGroup?.id;
                return (
                  <button
                    key={group.id}
                    type="button"
                    onClick={() => setActiveGroupId(group.id)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center justify-between gap-2 whitespace-nowrap rounded-sm px-3 py-2 text-left text-sm transition-colors",
                      active
                        ? "bg-accent-soft text-fg"
                        : "text-muted hover:bg-elevated hover:text-fg",
                    )}
                  >
                    <span className="truncate">{group.label}</span>
                    <span className="text-2xs tabular-nums text-subtle">
                      {group.items.length}
                    </span>
                  </button>
                );
              })}
            </div>
          </nav>

          <section className="min-w-0 flex-1 rounded-md border border-border bg-panel px-5">
            {activeGroup ? (
              <>
                <header className="flex items-center justify-between border-b border-border py-3">
                  <h2 className="text-sm font-semibold text-fg">
                    {activeGroup.label}
                  </h2>
                  <span className="text-2xs text-subtle">
                    {t("settingsPage.items", { n: activeGroup.items.length })}
                  </span>
                </header>
                <div className="divide-y divide-border">
                  {activeGroup.items.map((item) => (
                    <SettingsField
                      key={`${item.key}:${resetToken}`}
                      item={item}
                      value={values[item.key]}
                      invalid={Boolean(invalidKeys[item.key])}
                      onChange={(value) => update(item.key, value)}
                      onValidityChange={(valid) => markValidity(item.key, valid)}
                    />
                  ))}
                </div>
              </>
            ) : null}
          </section>
        </div>
      )}

      {saveError ? (
        <p className="mt-4 text-sm text-danger" role="alert">
          {saveError}
        </p>
      ) : null}
    </PageFrame>
  );
}
