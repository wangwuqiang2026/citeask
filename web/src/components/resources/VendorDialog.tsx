import { useMutation } from "@tanstack/react-query";
import { Loader2, PlugZap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { useT, type MessageKey } from "@/lib/i18n";
import type { VendorCatalogEntry, VendorEntry } from "@/lib/types";

const VENDOR_KIND_LABEL: Record<string, MessageKey> = {
  llms: "resources.llms",
  embeddings: "resources.embeddings",
  rerankings: "resources.rerankings",
};

interface VendorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  kind: string;
  catalog: VendorCatalogEntry[];
  entry: VendorEntry | null;
  onSaved: () => void;
}

function isBooleanType(type: string): boolean {
  return type.includes("bool");
}

function isNumberType(type: string): boolean {
  return type.includes("int") || type.includes("float");
}

function defaultsFor(vendor: VendorCatalogEntry | undefined): Record<string, unknown> {
  const values: Record<string, unknown> = {};
  for (const param of vendor?.params ?? []) {
    if (isBooleanType(param.type)) {
      values[param.name] = Boolean(param.default);
    } else if (param.default !== null && param.default !== undefined) {
      values[param.name] = String(param.default);
    } else {
      values[param.name] = "";
    }
  }
  return values;
}

function initialFor(entry: VendorEntry | null): Record<string, unknown> {
  const spec = { ...(entry?.spec ?? {}) };
  delete spec.__type__;
  const values: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(spec)) {
    values[key] = typeof value === "boolean" ? value : String(value ?? "");
  }
  return values;
}

export function VendorDialog({
  open,
  onOpenChange,
  kind,
  catalog,
  entry,
  onSaved,
}: VendorDialogProps) {
  const t = useT();
  const editing = entry !== null;

  const [name, setName] = useState("");
  const [vendor, setVendor] = useState("");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [isDefault, setIsDefault] = useState(false);
  const [advanced, setAdvanced] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testOk, setTestOk] = useState(false);

  const selectedVendor = useMemo(
    () => catalog.find((item) => item.name === vendor),
    [catalog, vendor],
  );

  // The supported models are shown where they belong: next to the picker that
  // creates one. The resources list itself only shows what the user added (§5.34).
  const supportedModels = useMemo(
    () =>
      catalog.map((entry) => {
        const model = entry.params.find((param) =>
          ["model", "model_name", "model_id", "model_path"].includes(param.name),
        )?.default;
        return typeof model === "string" && model
          ? `${entry.name}（${model}）`
          : entry.name;
      }),
    [catalog],
  );

  useEffect(() => {
    if (!open) return;
    const nextVendor = entry?.vendor ?? catalog[0]?.name ?? "";
    setName(entry?.name ?? "");
    setVendor(nextVendor);
    const spec = initialFor(entry);
    const defaults = defaultsFor(catalog.find((item) => item.name === nextVendor));
    setValues(entry ? { ...defaults, ...spec } : defaults);
    setIsDefault(entry?.default ?? false);
    setAdvanced("");
    setError(null);
    setTestResult(null);
  }, [open, entry, catalog]);

  const changeVendor = (next: string) => {
    setVendor(next);
    setValues(defaultsFor(catalog.find((item) => item.name === next)));
    setTestResult(null);
  };

  const collectParams = (): Record<string, unknown> | null => {
    const params: Record<string, unknown> = {};
    for (const param of selectedVendor?.params ?? []) {
      const raw = values[param.name];
      if (isBooleanType(param.type)) {
        params[param.name] = Boolean(raw);
        continue;
      }
      const text = String(raw ?? "").trim();
      if (!text) {
        if (param.required) {
          setError(`${param.name}: ${param.help || param.name}`);
          return null;
        }
        continue;
      }
      if (isNumberType(param.type)) {
        const parsed = Number(text);
        if (Number.isNaN(parsed)) {
          setError(`${param.name}: ${t("resources.numberInvalid")}`);
          return null;
        }
        params[param.name] = parsed;
      } else {
        params[param.name] = text;
      }
    }
    if (advanced.trim()) {
      try {
        const extra = JSON.parse(advanced);
        if (extra && typeof extra === "object" && !Array.isArray(extra)) {
          Object.assign(params, extra);
        }
      } catch {
        setError(t("resources.invalidJson"));
        return null;
      }
    }
    return params;
  };

  const save = useMutation({
    mutationFn: async () => {
      const params = collectParams();
      if (params === null) throw new Error("invalid");
      const body = {
        params,
        default: isDefault,
        ...(editing ? { new_name: name.trim() } : {}),
      };
      if (editing) {
        return api.updateVendor(kind, entry!.name, body);
      }
      return api.createVendor(kind, {
        ...body,
        name: name.trim(),
        vendor,
      });
    },
    onSuccess: () => {
      onOpenChange(false);
      onSaved();
    },
    onError: (mutationError: Error) => {
      if (mutationError.message !== "invalid") setError(mutationError.message);
    },
  });

  const submit = () => {
    setError(null);
    if (!name.trim()) {
      setError(t("resources.nameRequired"));
      return;
    }
    if (!vendor) {
      setError(t("resources.noVendors"));
      return;
    }
    save.mutate();
  };

  const test = async () => {
    const params = collectParams();
    if (params === null) return;
    setTestResult(null);
    try {
      const result = await api.testVendor(vendor, params);
      setTestOk(result.ok);
      setTestResult(result.message);
    } catch (testError) {
      setTestOk(false);
      setTestResult((testError as Error).message);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {editing ? t("resources.editModel") : t("resources.addModel")}
          </DialogTitle>
          <DialogDescription>
            {t(VENDOR_KIND_LABEL[kind] ?? "resources.tabModels")}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-2 space-y-3">
          <label className="block space-y-1">
            <span className="text-sm text-fg">{t("resources.modelName")}</span>
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </label>

          <label className="block space-y-1">
            <span className="text-sm text-fg">{t("resources.vendor")}</span>
            <select
              value={vendor}
              onChange={(event) => changeVendor(event.target.value)}
              className="h-9 w-full rounded-sm border border-border bg-panel px-2 text-sm text-fg focus-visible:border-accent focus-visible:outline-none"
            >
              {catalog.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name}
                </option>
              ))}
            </select>
            {supportedModels.length > 0 ? (
              <p className="text-2xs text-subtle">
                {t("resources.supportedModels", {
                  list: supportedModels.join(" · "),
                })}
              </p>
            ) : null}
          </label>

          <div className="space-y-3 rounded-md border border-border p-3">
            {(selectedVendor?.params ?? []).map((param) => (
              <div key={param.name} className="space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm text-fg">
                    {param.name}
                    {param.required ? (
                      <span className="ml-1 text-danger">*</span>
                    ) : null}
                  </span>
                  <span className="text-2xs text-subtle">{param.type}</span>
                </div>
                {isBooleanType(param.type) ? (
                  <Switch
                    checked={Boolean(values[param.name])}
                    onCheckedChange={(checked) =>
                      setValues((current) => ({ ...current, [param.name]: checked }))
                    }
                  />
                ) : (
                  <Input
                    type={
                      param.secret
                        ? "password"
                        : isNumberType(param.type)
                          ? "number"
                          : "text"
                    }
                    value={String(values[param.name] ?? "")}
                    onChange={(event) =>
                      setValues((current) => ({
                        ...current,
                        [param.name]: event.target.value,
                      }))
                    }
                    placeholder={param.secret ? "••••••" : ""}
                  />
                )}
                {param.help ? (
                  <p className="text-2xs text-subtle">{param.help}</p>
                ) : null}
              </div>
            ))}
          </div>

          <details className="rounded-md border border-border px-3 py-2">
            <summary className="cursor-pointer text-sm text-muted">
              {t("resources.advanced")}
            </summary>
            <p className="mt-1 text-2xs text-subtle">{t("resources.advancedHint")}</p>
            <Textarea
              rows={4}
              value={advanced}
              onChange={(event) => setAdvanced(event.target.value)}
              placeholder='{"key": "value"}'
              className="mt-2 font-mono text-xs"
            />
          </details>

          <div className="flex items-center justify-between gap-4 py-1">
            <span className="text-sm text-fg">{t("resources.setDefault")}</span>
            <Switch checked={isDefault} onCheckedChange={setIsDefault} />
          </div>

          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}
          {testResult ? (
            <p className={testOk ? "text-sm text-success" : "text-sm text-danger"}>
              {testResult}
            </p>
          ) : null}
        </div>

        <div className="mt-4 flex items-center justify-between gap-2">
          {kind === "llms" ? (
            <Button variant="ghost" size="sm" onClick={() => void test()}>
              <PlugZap className="h-4 w-4" aria-hidden="true" />
              {t("resources.test")}
            </Button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              {t("common.cancel")}
            </Button>
            <Button variant="primary" onClick={submit} disabled={save.isPending}>
              {save.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : null}
              {t("resources.save")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
