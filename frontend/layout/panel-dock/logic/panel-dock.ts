// Zavěšené panely Editoru bez Reactu: který panel je otevřený, co ho přepne a kam se dropdown
// posadí. Kontrakt `docs/rozvrzeni-editoru.md` (Dílek 2). Knihovna ani Agenti a postupy už nejsou
// sloupce v toku — visí pod svým tlačítkem v liště nástrojů a otevřený je vždy nejvýš jeden, aby
// plátno nikdy nezakrývaly dva najednou. Komponenty jen čtou výsledek; pravidla drží tento soubor.
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

/** Šířka panelu, okraj od hrany rámu, poloha šipky od levé hrany panelu a nejmenší odstup šipky od rohu. */
export const PANEL_WIDTH = 360;
export const PANEL_GAP = 8;
export const ARROW_INSET = 44;
export const ARROW_EDGE = 16;

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

/**
 * Kam dropdown posadit: šipka má stát 44 px od levé hrany panelu přímo pod středem tlačítka. U pravé
 * hrany rámu se panel zarazí 8 px před koncem a šipka se posune doprava, aby dál mířila na tlačítko;
 * nikdy ale nevjede do zaobleného rohu (16 px od obou hran). `anchorCenter` i `left` se měří od levé
 * hrany rámu, `arrow` od levé hrany panelu.
 */
export function dropdownPlacement(anchorCenter: number, frameWidth: number): { left: number; arrow: number } {
  const maxLeft = Math.max(PANEL_GAP, frameWidth - PANEL_WIDTH - PANEL_GAP);
  const left = clamp(anchorCenter - ARROW_INSET, PANEL_GAP, maxLeft);
  const arrow = clamp(anchorCenter - left, ARROW_EDGE, PANEL_WIDTH - ARROW_EDGE);
  return { left, arrow };
}
