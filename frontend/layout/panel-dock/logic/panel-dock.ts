// Šuplík Editoru bez Reactu: který panel je otevřený a co ho přepne. Kontrakt
// `docs/suplik-a-profil.md` (část 4). Knihovna ani Agenti a postupy nejsou sloupce v toku — vyjíždějí
// jako šuplík u levého okraje a otevřený je vždy nejvýš jeden, aby plátno nikdy nezakrývaly dva
// najednou. Komponenty jen čtou výsledek; pravidla drží tento soubor.
import { isLibraryCollapseShortcut, type ShortcutKey } from "@/layout/library-navbar/logic/library-navbar";
import { isCollapseShortcut } from "@/layout/agent-navbar/logic/agent-navbar";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";

export type DockPanel = "library" | "agents";

/** Pořadí tlačítek v liště: Knihovna vlevo od Agentů, stejně jako čárka leží vlevo od tečky. */
export const DOCK_PANELS: { key: DockPanel; label: string; icon: IconName; shortcut: string }[] = [
  { key: "library", label: "Knihovna", icon: "library", shortcut: "Ctrl+Shift+," },
  { key: "agents", label: "Agenti a postupy", icon: "bot", shortcut: "Ctrl+Shift+." },
];

/** Klik na tlačítko otevřeného panelu ho zavře; klik na druhé tlačítko panely rovnou vymění. */
export function togglePanel(open: DockPanel | null, panel: DockPanel): DockPanel | null {
  return open === panel ? null : panel;
}

/** Ctrl+Shift+, patří Knihovně, Ctrl+Shift+. Agentům; pravidla samotná bydlí u svých panelů. */
export function panelForShortcut(event: ShortcutKey): DockPanel | null {
  if (isLibraryCollapseShortcut(event)) return "library";
  if (isCollapseShortcut(event)) return "agents";
  return null;
}

/** Esc zavře otevřený panel. Jiná klávesa ne — panel nemá druhou cestu ven z klávesnice. */
export function isDismissKey(event: { key: string }): boolean {
  return event.key === "Escape";
}
