// Menu Editoru bez Reactu (docs/menu-a-katalog.md, část A): ☰ v liště otevře u levého okraje lištu
// ikon a vedle ní panel zvolené sekce. Tady jsou všechna pravidla, co který klik a která klávesa
// udělá; komponenty jen čtou výsledek. Otevřenost lišty se neukládá — po načtení stránky menu nikdy
// nezakrývá plátno. Pamatuje se jen poslední sekce, jednou pro celou aplikaci (`opora:panel-dock:v1`).
import { isLibraryCollapseShortcut, type ShortcutKey } from "@/layout/library-navbar/logic/library-navbar";
import { isCollapseShortcut } from "@/layout/agent-navbar/logic/agent-navbar";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";

export type DockSection = "library" | "agents" | "flows" | "settings";

/** Ikona lišty: ze sady `ui-kit/icon`, nebo jedna ze dvou vlastních značek menu (kreslí `DockIcon`). */
export type DockIconName = IconName | "menu" | "settings";

export type DockSectionInfo = {
  key: DockSection;
  label: string;
  icon: DockIconName;
  /** Zkratka do tooltipu; jen sekce, které ji mají. */
  shortcut?: string;
  /** Nastavení stojí v liště pod oddělovačem, odděleně od obsahu, ze kterého se bere. */
  apart?: boolean;
};

/** Kostra je návrh projektu; Knihovna a Agenti nabízejí podklady pro jeho práci. */
export const DOCK_SECTIONS: DockSectionInfo[] = [
  { key: "library", label: "Knihovna", icon: "library", shortcut: "Ctrl+Shift+," },
  { key: "agents", label: "Agenti", icon: "bot", shortcut: "Ctrl+Shift+." },
  { key: "flows", label: "Postupy", icon: "workflow" },
  { key: "settings", label: "Nastavení", icon: "settings", apart: true },
];

export const sectionInfo = (section: DockSection): DockSectionInfo =>
  DOCK_SECTIONS.find((item) => item.key === section) ?? DOCK_SECTIONS[0];

export type DockState = {
  /** Lišta ikon je vysunutá. */
  rail: boolean;
  /** Otevřený panel sekce, nebo `null`, když je vidět jen lišta. */
  section: DockSection | null;
  /** Poslední otevřená sekce; ☰ ji otevře rovnou. Jediné, co se ukládá. */
  last: DockSection | null;
};

export const closedDock = (last: DockSection | null = null): DockState => ({ rail: false, section: null, last });

/** ☰: zavřené menu otevře (i s poslední sekcí), otevřené zavře celé — lištu i panel. */
export function toggleMenu(state: DockState): DockState {
  if (state.rail) return closedDock(state.last);
  return { rail: true, section: state.last, last: state.last };
}

/** Ikona v liště: neaktivní sekci otevře, aktivní panel sbalí a lišta zůstane. */
export function selectSection(state: DockState, section: DockSection): DockState {
  if (state.section === section) return { ...state, rail: true, section: null };
  return { rail: true, section, last: section };
}

/** Zkratka sekce otevře lištu rovnou na sekci; když už sekce svítí, chová se jako klik na její ikonu. */
export const shortcutSection = selectSection;

/** Esc zavře nejdřív panel, pak lištu. Zavřené menu nechá být. */
export function dismissDock(state: DockState): DockState {
  if (state.section) return { ...state, section: null };
  if (state.rail) return closedDock(state.last);
  return state;
}

/** Ctrl+Shift+, patří Knihovně, Ctrl+Shift+. Agentům; pravidla samotná bydlí u svých panelů. */
export function sectionForShortcut(event: ShortcutKey): DockSection | null {
  if (isLibraryCollapseShortcut(event)) return "library";
  if (isCollapseShortcut(event)) return "agents";
  return null;
}

export function isDismissKey(event: { key: string }): boolean {
  return event.key === "Escape";
}

/** Jediný klíč pro celou aplikaci. Nikdy se do něj nepřidává id projektu. */
export const PANEL_DOCK_KEY = "opora:panel-dock:v1";

const KNOWN = new Set<string>(DOCK_SECTIONS.map((item) => item.key));

/** Uložená sekce je cizí text: neznámá hodnota nebo rozbitý JSON znamená „žádná“. */
export function parseDockSection(raw: string | null): DockSection | null {
  try {
    const value = raw ? (JSON.parse(raw) as { section?: unknown } | null) : null;
    if (value?.section === "skeleton") return "library";
    return value && typeof value.section === "string" && KNOWN.has(value.section) ? (value.section as DockSection) : null;
  } catch {
    return null;
  }
}

/** Compatibility: the old separate tree now opens Library > Structure without touching graph data. */
export function readLegacySkeletonPreference(): boolean {
  try { return JSON.parse(localStorage.getItem(PANEL_DOCK_KEY) ?? "null")?.section === "skeleton"; }
  catch { return false; }
}

export function readDockSection(): DockSection | null {
  try {
    return parseDockSection(localStorage.getItem(PANEL_DOCK_KEY));
  } catch {
    return null;
  }
}

export function writeDockSection(section: DockSection | null): boolean {
  try {
    localStorage.setItem(PANEL_DOCK_KEY, JSON.stringify({ section }));
    return true;
  } catch {
    return false;
  }
}
