import { useEffect, useRef, useState, useSyncExternalStore } from "react";

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

const THEMES: { id: DesktopTheme; label: string }[] = [{ id: "light", label: "Světlý" }, { id: "dark", label: "Tmavý" }];
const DENSITIES: { id: DesktopDensity; label: string }[] = [
  { id: "compact", label: "Kompaktní" }, { id: "normal", label: "Normální" }, { id: "airy", label: "Vzdušná" },
];

/** Jedno tiché tlačítko v horní liště; režim a hustota jsou preference prohlížeče, ne projektu. */
export default function DesktopThemeControls() {
  const appearance = useDesktopAppearance();
  const [open, setOpen] = useState(false);
  const anchor = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => { if (!anchor.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", escape); };
  }, [open]);
  return <div className="v3-appearance" ref={anchor}>
    <button type="button" className="v3-appearance-button" aria-haspopup="true" aria-expanded={open}
      title={appearance.theme === "light" ? "Světlý režim" : "Tmavý režim"} onClick={() => setOpen((value) => !value)}>Vzhled</button>
    {open && <div className="v3-appearance-menu" role="group" aria-label="Vzhled rozhraní">
      <div className="menu-head">Barevný režim</div>
      <div className="v3-segment">{THEMES.map((item) => <button type="button" key={item.id} aria-pressed={appearance.theme === item.id}
        onClick={() => setAppearance({ theme: item.id })}>{item.label}</button>)}</div>
      <div className="menu-head">Hustota</div>
      <div className="v3-segment">{DENSITIES.map((item) => <button type="button" key={item.id} aria-pressed={appearance.density === item.id}
        onClick={() => setAppearance({ density: item.id })}>{item.label}</button>)}</div>
      <p className="muted">Ukládá se jen v tomto prohlížeči.</p>
    </div>}
  </div>;
}
