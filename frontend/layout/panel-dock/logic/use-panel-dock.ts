// Vazba menu Editoru na React. Hook nemá vlastní pravidla: drží jeden stav (lišta, panel, poslední
// sekce), mění ho funkcemi z panel-dock.ts a váže jeden posluchač `keydown` na `window` pro obě
// zkratky i Esc. Ukládá se jen poslední sekce, jednou pro aplikaci; otevřenost ne — po načtení
// stránky menu nikdy nezakrývá plátno. Volá ho rodič (App) jednou a rozdá výsledek dílkům v props.
import { useCallback, useEffect, useRef, useState } from "react";
import {
  closedDock,
  dismissDock,
  isDismissKey,
  readDockSection,
  sectionForShortcut,
  selectSection,
  shortcutSection,
  toggleMenu,
  writeDockSection,
  type DockSection,
} from "./panel-dock";
import { isTypingTarget } from "@/editor/canvas/history/logic/undo-shortcut";

export type PanelDockApi = {
  /** Lišta ikon je vysunutá. */
  rail: boolean;
  /** Otevřený panel sekce, nebo `null`. */
  section: DockSection | null;
  /** ☰ v liště nástrojů. */
  toggleMenu: () => void;
  /** Ikona v liště ikon (a odkaz „Nastavit“ v hlavičce projektu). */
  select: (section: DockSection) => void;
  /** Zavře lištu i panel: klik do horní lišty, přepnutí módu, odchod z Editoru. */
  close: () => void;
};

export function usePanelDock(enabled: boolean): PanelDockApi {
  const [state, setState] = useState(() => closedDock(readDockSection()));
  // Mimo Editor menu není kam vysunout: odchod do Projektu nebo Live Runu ho zavře.
  useEffect(() => {
    if (!enabled) setState((current) => (current.rail ? closedDock(current.last) : current));
  }, [enabled]);
  useEffect(() => { writeDockSection(state.last); }, [state.last]);
  // Posluchač se váže jednou; `enabled` se čte z ref, aby překreslení plochy neměnilo zkratky.
  const active = useRef(enabled);
  active.current = enabled;
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (!active.current) return;
      // Kdo píše do pole nebo textu, si klávesy hlídá sám; plocha mu je nebere.
      if (isTypingTarget(event.target)) return;
      const section = sectionForShortcut(event);
      if (section) {
        event.preventDefault();
        setState((current) => shortcutSection(current, section));
      } else if (isDismissKey(event)) {
        setState(dismissDock);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const menu = useCallback(() => setState(toggleMenu), []);
  const select = useCallback((section: DockSection) => setState((current) => selectSection(current, section)), []);
  const close = useCallback(() => setState((current) => (current.rail ? closedDock(current.last) : current)), []);
  return { rail: state.rail, section: state.section, toggleMenu: menu, select, close };
}
