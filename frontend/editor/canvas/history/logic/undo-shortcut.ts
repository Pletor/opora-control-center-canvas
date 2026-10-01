// Klávesa pro krok zpět na plátně. Pravidlo, která klávesa co znamená a kdy se nesmí chytit, je
// čistá funkce (testovaná bez DOM); hook kolem ní jen drží jeden posluchač na `window`, aby plátno
// nemělo víc míst, kde se Ctrl+Z vykládá.
import { useEffect, useRef } from "react";

/** Co uživatel klávesou chtěl; `null` znamená „tahle klávesa nám nepatří, nech ji projít“. */
export type UndoIntent = "undo" | "redo" | null;

/** Jen ta část události, na které pravidlo stojí — díky tomu jde přečíst i z prostého objektu v testu. */
export type ShortcutKey = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey">;

/**
 * Ctrl+Z (na Macu ⌘Z) je krok zpět, Ctrl+Shift+Z i Ctrl+Y krok vpřed. Alt drží stranou jiné zkratky
 * plátna (Alt+1..3 přepíná prostředí), samotné Z bez modifikátoru patří psaní, ne historii.
 */
export function undoIntent(event: ShortcutKey): UndoIntent {
  if (event.altKey) return null;
  if (!event.ctrlKey && !event.metaKey) return null;
  const key = event.key.toLowerCase();
  if (key === "z") return event.shiftKey ? "redo" : "undo";
  if (key === "y" && !event.shiftKey) return "redo";
  return null;
}

/**
 * Píše uživatel do něčeho vlastního? Pole, textarea, výběr a editovatelný text mají svůj vlastní
 * krok zpět (prohlížeč vrací napsaná písmena) a plátno jim ho nesmí vzít. Stejně se chová všechno
 * uvnitř prvku označeného `data-no-undo` — tím se zvenčí vypne historie i pro cizí editor.
 */
export function isTypingTarget(target: unknown): boolean {
  if (!target || typeof target !== "object") return false;
  const element = target as { tagName?: unknown; isContentEditable?: unknown; closest?: unknown };
  const tag = typeof element.tagName === "string" ? element.tagName.toUpperCase() : "";
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (element.isContentEditable === true) return true;
  if (typeof element.closest !== "function") return false;
  const closest = element.closest as (selector: string) => unknown;
  try {
    return !!closest("[data-no-undo], input, textarea, select, [contenteditable]");
  } catch {
    return false;
  }
}

/**
 * Jeden posluchač na `window` po celou dobu, co má plátno co vracet. `enabled` drží rodič (plátno
 * Editoru, které se dá měnit a zrovna neukládá); dokud je `false`, zkratka neexistuje a Ctrl+Z jde
 * dál, kam patřil. Obsluha se čte z ref, takže nový graf nepřepisuje posluchač při každém překreslení.
 */
export function useUndoShortcut({ enabled, onUndo, onRedo }: {
  enabled: boolean;
  onUndo: () => void;
  onRedo: () => void;
}) {
  const handlers = useRef({ onUndo, onRedo });
  handlers.current = { onUndo, onRedo };
  useEffect(() => {
    if (!enabled) return;
    const key = (event: KeyboardEvent) => {
      const intent = undoIntent(event);
      if (!intent) return;
      if (isTypingTarget(event.target)) return;
      event.preventDefault();
      if (intent === "undo") handlers.current.onUndo();
      else handlers.current.onRedo();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [enabled]);
}
