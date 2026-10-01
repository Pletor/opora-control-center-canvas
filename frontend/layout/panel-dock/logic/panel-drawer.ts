// Výběr v šuplíku bez Reactu (docs/suplik-a-profil.md, část 4): „Pro tento projekt“ ukáže jen prvky,
// které k profilu sedí, „Vše“ celý katalog. Prvky mimo profil se dají dočasně ukázat řádkem pod
// seznamem a hledání je prohledává vždy — výsledek mimo profil jen ztlumí. Volba filtru je
// preference rozhraní, proto se ukládá jednou pro aplikaci pod `opora:panel-drawer:v1`, nikdy
// s klíčem projektu. Knihovna i Agenti volají tutéž funkci, aby se filtrovaly stejně.
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import { profileUnset } from "@/shared/project-capabilities/logic/project-capabilities";
import { fitReason, splitByProfile, type Fittable } from "@/editor/component-library/library-catalog/logic/catalog-fit";

export type CatalogScope = "fitting" | "all";

export type CatalogScopeOptions = {
  scope: CatalogScope;
  /** Řádek „Mimo profil · zobrazit“: dočasně ukáže i prvky mimo profil. */
  showOutside: boolean;
  query: string;
};

export type CatalogView<T> = {
  /** Co seznam vypíše, v pořadí katalogu. */
  shown: T[];
  /** Co je mimo profil a seznam to právě schovává; podle toho se kreslí řádek pod seznamem. */
  hidden: T[];
  /** Mimo profil vůbec (i když je to právě vidět): tyhle prvky seznam ztlumí. */
  outside: T[];
  /** Čísla pro přepínač „Pro tento projekt N“ / „Vše M“. */
  fittingCount: number;
  allCount: number;
  /** Má smysl ukazovat přepínač a řádek mimo profil? Nenastavený profil nic nefiltruje. */
  filtering: boolean;
};

/**
 * Rozdělí katalog podle profilu a vybere, co je vidět. `search` je hledání toho katalogu (Knihovna
 * i Agenti mají vlastní) a pouští se vždy nad celým katalogem, aby hledání našlo i prvky mimo profil.
 */
export function catalogView<T extends Fittable>(
  items: T[],
  profile: ProjectProfile,
  options: CatalogScopeOptions,
  search: (items: T[], query: string) => T[],
): CatalogView<T> {
  const { fitting, outside } = splitByProfile(items, profile);
  const filtering = !profileUnset(profile);
  const searching = options.query.trim().length > 0;
  const showAll = !filtering || searching || options.scope === "all" || options.showOutside;
  const shown = search(showAll ? items : fitting, options.query);
  return {
    shown,
    hidden: showAll ? [] : outside,
    outside: filtering ? outside : [],
    fittingCount: fitting.length,
    allCount: items.length,
    filtering,
  };
}

/** Poznámka k prvku v seznamu: „mimo profil“, „kvůli profilu: …“, nebo nic u univerzálního. */
export function fitNote(item: Fittable, profile: ProjectProfile, outside: ReadonlySet<Fittable>): string | null {
  if (outside.has(item)) return "mimo profil";
  return fitReason(item, profile);
}

/**
 * Skupina je ve výběru jen kvůli profilu, když každý její vybraný prvek má důvod „kvůli profilu“.
 * Taková skupina nese štítek a stojí v seznamu nahoře — je to to, co projekt odlišuje od ostatních.
 */
export function profileOnlyGroup(items: Fittable[], profile: ProjectProfile): boolean {
  return items.length > 0 && items.every((item) => fitReason(item, profile) !== null);
}

/** Jediný klíč pro celou aplikaci. Nikdy se do něj nepřidává id projektu. */
export const PANEL_DRAWER_KEY = "opora:panel-drawer:v1";

export function parseCatalogScope(raw: string | null): CatalogScope {
  try {
    const value = raw ? (JSON.parse(raw) as { scope?: unknown } | null) : null;
    return value && value.scope === "all" ? "all" : "fitting";
  } catch {
    return "fitting";
  }
}

export function readCatalogScope(): CatalogScope {
  try {
    return parseCatalogScope(localStorage.getItem(PANEL_DRAWER_KEY));
  } catch {
    return "fitting";
  }
}

export function writeCatalogScope(scope: CatalogScope): boolean {
  try {
    localStorage.setItem(PANEL_DRAWER_KEY, JSON.stringify({ scope }));
    return true;
  } catch {
    return false;
  }
}
