import { useSyncExternalStore } from "react";

/** Vzhled rozhraní: barevný režim a hustota. Preference prohlížeče, ne projektu; ovládá se v Nastavení → Obecné. */
export type DesktopTheme = "light" | "dark";
export type DesktopDensity = "compact" | "normal" | "airy";
export type DesktopAppearance = { theme: DesktopTheme; density: DesktopDensity };
/** Stejný klíč čte inline bootstrap v index.html, aby první vykreslení nebliklo. */
export const APPEARANCE_KEY = "opora:desktop-theme:v1";

export function readAppearance(): DesktopAppearance {
  let stored: Partial<DesktopAppearance> = {};
  try {
    stored = JSON.parse(localStorage.getItem(APPEARANCE_KEY) ?? "null") ?? {};
  } catch {
    /* Poškozená preference vzhledu není projektová data. */
  }
  const systemLight = typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: light)").matches;
  return {
    theme: stored.theme === "light" || stored.theme === "dark" ? stored.theme : systemLight ? "light" : "dark",
    density: stored.density === "compact" || stored.density === "airy" ? stored.density : "normal",
  };
}

function apply(value: DesktopAppearance) {
  const root = document.documentElement;
  root.dataset.theme = value.theme;
  root.dataset.density = value.density;
  root.style.colorScheme = value.theme;
}

let current = readAppearance();
const listeners = new Set<() => void>();
apply(current);
if (typeof window !== "undefined") {
  window.addEventListener("storage", (event) => {
    if (event.key !== APPEARANCE_KEY) return;
    current = readAppearance();
    apply(current);
    listeners.forEach((listener) => listener());
  });
}

export function setAppearance(update: Partial<DesktopAppearance>) {
  current = { ...current, ...update };
  apply(current);
  try {
    localStorage.setItem(APPEARANCE_KEY, JSON.stringify(current));
  } catch {
    /* Vzhled platí v této relaci i bez úložiště prohlížeče. */
  }
  listeners.forEach((listener) => listener());
}

export function useDesktopAppearance(): DesktopAppearance {
  return useSyncExternalStore(
    (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
    () => current,
  );
}
