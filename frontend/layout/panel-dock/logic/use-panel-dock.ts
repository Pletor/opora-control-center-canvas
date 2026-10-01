// Vazba šuplíku Editoru na React. Hook nemá vlastní pravidla: drží jednu hodnotu (který panel je
// otevřený), mění ji funkcemi z panel-dock.ts a váže jeden posluchač `keydown` na `window` pro obě
// zkratky i Esc. Stav je jen v paměti sezení a nikam se neukládá — po načtení stránky panel nikdy
// nezakrývá plátno. Volá ho rodič (App) jednou a rozdá výsledek dílkům v props.
import { useCallback, useEffect, useRef, useState } from "react";
import { isDismissKey, panelForShortcut, togglePanel, type DockPanel } from "./panel-dock";
import { isTypingTarget } from "@/editor/canvas/history/logic/undo-shortcut";

export type PanelDockApi = {
  open: DockPanel | null;
  /** Tlačítko v liště i zkratka: zavřený panel otevře, otevřený zavře, druhý vymění. */
  toggle: (panel: DockPanel) => void;
  /** Křížek v hlavičce, Esc, klik mimo panel, přepnutí módu i odchod z Editoru. */
  close: () => void;
};

export function usePanelDock(enabled: boolean): PanelDockApi {
  const [open, setOpen] = useState<DockPanel | null>(null);
  // Mimo Editor panel není kam zavěsit: odchod do Projektu nebo Live Runu ho zavře.
  useEffect(() => {
    if (!enabled) setOpen(null);
  }, [enabled]);
  // Posluchač se váže jednou; `enabled` se čte z ref, aby překreslení plochy neměnilo zkratky.
  const active = useRef(enabled);
  active.current = enabled;
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (!active.current) return;
      // Kdo píše do pole nebo textu, si klávesy hlídá sám; plocha mu je nebere.
      if (isTypingTarget(event.target)) return;
      const panel = panelForShortcut(event);
      if (panel) {
        event.preventDefault();
        setOpen((current) => togglePanel(current, panel));
      } else if (isDismissKey(event)) {
        setOpen(null);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const toggle = useCallback((panel: DockPanel) => setOpen((current) => togglePanel(current, panel)), []);
  const close = useCallback(() => setOpen(null), []);
  return { open, toggle, close };
}
