import { useEffect, useState } from "react";

import { Input, Textarea } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useT } from "@/lib/i18n";
import {
  fromSelectValue,
  isLongText,
  parseNumberInput,
  toSelectValue,
} from "@/lib/settings";
import type { SettingsItem } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SettingsFieldProps {
  item: SettingsItem;
  value: unknown;
  invalid?: boolean;
  onChange: (value: unknown) => void;
  onValidityChange?: (valid: boolean) => void;
}

/**
 * One schema item → one labelled control. The backend declares the control type,
 * the label (already localized) and the choices; this component never invents a
 * setting. `number` keeps its raw text locally so the user can type freely and
 * still get an inline error.
 */
export function SettingsField({
  item,
  value,
  invalid = false,
  onChange,
  onValidityChange,
}: SettingsFieldProps) {
  const t = useT();
  const id = `setting-${item.key.replace(/[^a-z0-9]+/gi, "-")}`;
  const choices = item.choices ?? [];
  const label = (
    <div className="min-w-0">
      <label htmlFor={id} className="block text-sm font-medium text-fg">
        {item.label}
      </label>
      {item.info ? (
        <p className="mt-0.5 text-xs leading-relaxed text-subtle">{item.info}</p>
      ) : null}
    </div>
  );

  if (item.type === "checkbox") {
    return (
      <div className="flex items-center justify-between gap-4 py-3">
        {label}
        <Switch
          id={id}
          checked={Boolean(value)}
          onCheckedChange={(checked) => onChange(checked)}
        />
      </div>
    );
  }

  let control: React.ReactNode;
  switch (item.type) {
    case "number":
      control = (
        <NumberControl
          id={id}
          value={value}
          invalid={invalid}
          onChange={onChange}
          onValidityChange={onValidityChange}
        />
      );
      break;
    case "dropdown":
      control =
        choices.length > 0 ? (
          <Select
            value={toSelectValue(value)}
            onValueChange={(next) => onChange(fromSelectValue(next))}
          >
            <SelectTrigger id={id} className="mt-1.5 max-w-md">
              <SelectValue placeholder={t("settingsPage.default")} />
            </SelectTrigger>
            <SelectContent>
              {choices.map((choice) => (
                <SelectItem
                  key={String(choice.value)}
                  value={toSelectValue(choice.value)}
                >
                  {choice.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Input
            id={id}
            value={String(value ?? "")}
            onChange={(event) => onChange(event.target.value)}
            className="mt-1.5 max-w-md"
          />
        );
      break;
    case "radio":
      control = (
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2" role="radiogroup" aria-labelledby={id}>
          {choices.map((choice) => (
            <label
              key={String(choice.value)}
              className="inline-flex cursor-pointer items-center gap-2 text-sm text-fg"
            >
              <input
                type="radio"
                name={id}
                value={String(choice.value)}
                checked={String(value ?? "") === String(choice.value)}
                onChange={() => onChange(choice.value)}
                className="h-3.5 w-3.5 accent-[var(--color-accent)]"
              />
              {choice.label}
            </label>
          ))}
        </div>
      );
      break;
    case "checkboxgroup": {
      const selected = Array.isArray(value) ? value.map(String) : [];
      control = (
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
          {choices.map((choice) => {
            const choiceValue = String(choice.value);
            const checked = selected.includes(choiceValue);
            return (
              <label
                key={choiceValue}
                className="inline-flex cursor-pointer items-center gap-2 text-sm text-fg"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() =>
                    onChange(
                      checked
                        ? selected.filter((entry) => entry !== choiceValue)
                        : [...selected, choiceValue],
                    )
                  }
                  className="h-3.5 w-3.5 accent-[var(--color-accent)]"
                />
                {choice.label}
              </label>
            );
          })}
        </div>
      );
      break;
    }
    case "text":
    default:
      control = isLongText(item) ? (
        <Textarea
          id={id}
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
          rows={5}
          className="mt-1.5 font-mono text-xs leading-relaxed"
        />
      ) : (
        <Input
          id={id}
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
          className="mt-1.5 max-w-md"
        />
      );
      break;
  }

  return (
    <div className={cn("py-3", invalid && "text-danger")}>
      {label}
      {control}
      {invalid ? (
        <p className="mt-1 text-xs text-danger" role="alert">
          {t("settingsPage.numberInvalid")}
        </p>
      ) : null}
    </div>
  );
}

function NumberControl({
  id,
  value,
  invalid,
  onChange,
  onValidityChange,
}: {
  id: string;
  value: unknown;
  invalid: boolean;
  onChange: (value: unknown) => void;
  onValidityChange?: (valid: boolean) => void;
}) {
  const [raw, setRaw] = useState(
    typeof value === "number" ? String(value) : String(value ?? ""),
  );

  useEffect(() => {
    // the parent may reset the form (discard); mirror its value when it is a number
    if (typeof value === "number" && parseNumberInput(raw) !== value) {
      setRaw(String(value));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return (
    <Input
      id={id}
      inputMode="numeric"
      value={raw}
      aria-invalid={invalid}
      onChange={(event) => {
        const next = event.target.value;
        setRaw(next);
        const parsed = parseNumberInput(next);
        onValidityChange?.(parsed !== null);
        if (parsed !== null) onChange(parsed);
      }}
      className="mt-1.5 max-w-40 font-mono tabular-nums"
    />
  );
}
