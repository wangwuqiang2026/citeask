import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { VendorEntry } from "@/lib/types";

interface McpDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entry: VendorEntry | null;
  onSaved: () => void;
}

/**
 * MCP servers are free-form JSON configurations (command/args/env or a URL), so
 * the web UI edits the JSON directly instead of generating a form for every
 * transport the upstream MCP spec allows.
 */
export function McpDialog({ open, onOpenChange, entry, onSaved }: McpDialogProps) {
  const t = useT();
  const editing = entry !== null;

  const [name, setName] = useState("");
  const [config, setConfig] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(entry?.name ?? "");
    setConfig(JSON.stringify(entry?.config ?? { command: "", args: [] }, null, 2));
    setError(null);
  }, [open, entry]);

  const save = useMutation({
    mutationFn: () => {
      const parsed = JSON.parse(config);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error(t("resources.invalidJson"));
      }
      return editing
        ? api.updateVendor("mcp", entry!.name, { new_name: name.trim(), config: parsed })
        : api.createVendor("mcp", { name: name.trim(), config: parsed });
    },
    onSuccess: () => {
      onOpenChange(false);
      onSaved();
    },
    onError: (mutationError: Error) => setError(mutationError.message),
  });

  const submit = () => {
    setError(null);
    if (!name.trim()) {
      setError(t("resources.nameRequired"));
      return;
    }
    try {
      JSON.parse(config);
    } catch {
      setError(t("resources.invalidJson"));
      return;
    }
    save.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {editing ? t("resources.editMcp") : t("resources.addMcp")}
          </DialogTitle>
          <DialogDescription>{t("resources.mcpHint")}</DialogDescription>
        </DialogHeader>

        <div className="mt-2 space-y-3">
          <label className="block space-y-1">
            <span className="text-sm text-fg">{t("resources.modelName")}</span>
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className="block space-y-1">
            <span className="text-sm text-fg">{t("resources.mcpConfig")}</span>
            <Textarea
              rows={10}
              value={config}
              onChange={(event) => setConfig(event.target.value)}
              className="font-mono text-xs"
              spellCheck={false}
            />
          </label>
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button variant="primary" onClick={submit} disabled={save.isPending}>
            {t("resources.save")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
