import type { SettingsItem, SettingsSchema } from "./types";

/**
 * Pure helpers of the settings page.
 *
 * Three details of the backend contract live here so they are testable:
 *
 * * every value is a flat ``key -> value`` map; the schema only supplies labels,
 *   control types, defaults and choices;
 * * an empty-string choice is meaningful ("use the default model"), but Radix
 *   Select refuses empty item values, hence the sentinel round-trip;
 * * only changed keys are sent, because the service merges them into the stored
 *   row (sending everything would overwrite values written by another tab).
 */

/** Radix Select item value that stands in for the backend's empty string. */
export const DEFAULT_CHOICE_VALUE = "__default__";

export function toSelectValue(value: unknown): string {
  if (value === null || value === undefined) return DEFAULT_CHOICE_VALUE;
  const text = String(value);
  return text === "" ? DEFAULT_CHOICE_VALUE : text;
}

export function fromSelectValue(value: string): string {
  return value === DEFAULT_CHOICE_VALUE ? "" : value;
}

function defaultValue(item: SettingsItem): unknown {
  switch (item.type) {
    case "checkbox":
      return false;
    case "checkboxgroup":
      return [];
    case "number":
      return 0;
    default:
      return "";
  }
}

/** The defaults declared by the schema (used for keys the server omits). */
export function schemaDefaults(schema: SettingsSchema | undefined): Record<string, unknown> {
  const output: Record<string, unknown> = {};
  for (const group of schema?.groups ?? []) {
    for (const item of group.items) {
      output[item.key] = item.value === undefined ? defaultValue(item) : item.value;
    }
  }
  return output;
}

/** Schema defaults overlaid with the stored values — what the form starts from. */
export function mergeSettings(
  schema: SettingsSchema | undefined,
  values: Record<string, unknown> | undefined,
): Record<string, unknown> {
  return { ...schemaDefaults(schema), ...(values ?? {}) };
}

export function isSameValue(first: unknown, second: unknown): boolean {
  if (Array.isArray(first) && Array.isArray(second)) {
    return (
      first.length === second.length && first.every((item, index) => item === second[index])
    );
  }
  return first === second;
}

/** The subset of ``current`` that differs from ``initial``, for the PUT body. */
export function changedSettings(
  initial: Record<string, unknown>,
  current: Record<string, unknown>,
  keys: string[],
): Record<string, unknown> {
  const changed: Record<string, unknown> = {};
  for (const key of keys) {
    if (!isSameValue(initial[key], current[key])) changed[key] = current[key];
  }
  return changed;
}

/**
 * Prompt-like values get a textarea. The backend does not mark them, so the
 * heuristic is "long default value, or a key that names a prompt".
 */
export function isLongText(item: SettingsItem): boolean {
  const value = typeof item.value === "string" ? item.value : "";
  return value.length > 80 || value.includes("\n") || /prompt/i.test(item.key);
}

/** ``""`` / garbage → ``null`` so the form can show a validation error. */
export function parseNumberInput(raw: string): number | null {
  const text = raw.trim();
  if (!text) return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : null;
}

/** Flatten every key the schema renders, in form order. */
export function settingKeys(schema: SettingsSchema | undefined): string[] {
  return (schema?.groups ?? []).flatMap((group) => group.items.map((item) => item.key));
}
