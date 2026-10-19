import type { ThemeMode } from "@/stores/ui";

/** Applied by `App` on mount and whenever the stored mode changes. */
export function resolveDark(theme: ThemeMode): boolean {
  if (theme === "dark") return true;
  if (theme === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function applyTheme(theme: ThemeMode): boolean {
  const dark = resolveDark(theme);
  const root = document.documentElement;
  root.classList.toggle("dark", dark);
  root.style.colorScheme = dark ? "dark" : "light";
  return dark;
}

/** Keeps `system` live when the OS preference changes. Returns a cleanup fn. */
export function watchSystemTheme(theme: ThemeMode, onChange: () => void): () => void {
  if (theme !== "system" || !window.matchMedia) return () => undefined;
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const listener = () => onChange();
  media.addEventListener("change", listener);
  return () => media.removeEventListener("change", listener);
}
