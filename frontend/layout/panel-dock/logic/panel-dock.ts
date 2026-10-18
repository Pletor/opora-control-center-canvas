// Menu Editoru bez Reactu (docs/menu-a-katalog.md, část A): ☰ v liště otevře u levého okraje lištu
// ikon a vedle ní panel zvolené sekce. Tady jsou všechna pravidla, co který klik a která klávesa
// udělá; komponenty jen čtou výsledek. Otevřenost lišty se neukládá — po načtení stránky menu nikdy
// nezakrývá plátno. Pamatuje se jen poslední sekce, jednou pro celou aplikaci (`opora:panel-dock:v1`).
import type { ShortcutKey } from "@/editor/canvas/history/logic/undo-shortcut";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";

export type DockSection = "structure" | "vault" | "settings";

/** Ikona lišty: ze sady `ui-kit/icon`, nebo jedna z vlastních značek menu (kreslí `DockIcon`). */
export type DockIconName = IconName | "menu" | "settings" | "vault";

export type DockSectionInfo = {
  key: DockSection;
  label: string;
  icon: DockIconName;
  /** Zkratka do tooltipu; jen sekce, které ji mají. */
  shortcut?: string;
  /** Nastavení stojí v liště pod oddělovačem, odděleně od obsahu, ze kterého se bere. */
  apart?: boolean;
  /** Široký panel (Schránka má vlastní vnitřní menu a sekci naplno). */
  wide?: boolean;
};

/** Struktura je návrh projektu (strom vrstev a co dostane agent vybrané karty), Schránka drží jeho zadání. */
export const DOCK_SECTIONS: DockSectionInfo[] = [
  { key: "structure", label: "Struktura", icon: "layout-grid", shortcut: "Ctrl+Shift+," },
  { key: "vault", label: "Schránka", icon: "vault", shortcut: "Ctrl+Shift+.", wide: true },
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

/** Odkaz odjinud (čip „Ze schránky“ v detailu karty) otevře lištu rovnou na sekci; nikdy ji nesbalí. */
export function openSection(state: DockState, section: DockSection): DockState {
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

/** Zkratka menu: Ctrl (na Macu ⌘) + Shift a jedna klávesa; Alt drží stranou jiné zkratky plochy (Alt+1..3). */
function modified(event: ShortcutKey): boolean {
  return !event.altKey && (event.ctrlKey || event.metaKey) && event.shiftKey;
}

/**
 * Ctrl+Shift+, patří Struktuře a Ctrl+Shift+. Schránce: čárka je na klávesnici vlevo od tečky tak,
 * jako je Struktura v liště nad Schránkou. Podle rozložení klávesnice přijde „,“/„<“ nebo „.“/„>“,
 * proto platí obojí.
 */
export function sectionForShortcut(event: ShortcutKey): DockSection | null {
  if (!modified(event)) return null;
  if (event.key === "," || event.key === "<") return "structure";
  if (event.key === "." || event.key === ">") return "vault";
  return null;
}

export function isDismissKey(event: { key: string }): boolean {
  return event.key === "Escape";
}

/** Jediný klíč pro celou aplikaci. Nikdy se do něj nepřidává id projektu. */
export const PANEL_DOCK_KEY = "opora:panel-dock:v1";

const KNOWN = new Set<string>(DOCK_SECTIONS.map((item) => item.key));
/** Sekce zrušených menu (Knihovna, Agenti, Postupy, starý strom) se otevřou jako Struktura. */
const LEGACY = new Set(["library", "agents", "flows", "skeleton"]);

/** Uložená sekce je cizí text: neznámá hodnota nebo rozbitý JSON znamená „žádná“. */
export function parseDockSection(raw: string | null): DockSection | null {
  try {
    const value = raw ? (JSON.parse(raw) as { section?: unknown } | null) : null;
    if (typeof value?.section === "string" && LEGACY.has(value.section)) return "structure";
    return value && typeof value.section === "string" && KNOWN.has(value.section) ? (value.section as DockSection) : null;
  } catch {
    return null;
  }
}

export function readDockSection(): DockSection | null {
  try {
    return parseDockSection(localStorage.getItem(PANEL_DOCK_KEY));
  } catch {
    return null;
  }
}

/** Klíče smazaných sekcí (Agenti a Postupy, filtr katalogu): nikdo je nečte, při zápisu menu se uklidí. */
export const ORPHAN_KEYS = ["opora:agent-navbar:v1", "opora:panel-drawer:v1"];

export function writeDockSection(section: DockSection | null): boolean {
  try {
    localStorage.setItem(PANEL_DOCK_KEY, JSON.stringify({ section }));
    for (const key of ORPHAN_KEYS) localStorage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}
