// Katalog knihovny levého navbaru: data a čisté funkce nad nimi. Položka není obrázek v panelu,
// je to know-how: co musí a nesmí platit (`rules`), na jaké dílky se to rozpadá (`decomposition`)
// a jak vypadá kostra kódu (`template`). Panel ani plátno si nic nevymýšlí — dlaždice mimo katalog
// neexistuje. Kategorie odpovídají blokům 2–10 sektoru „Drag&drop-knihovna-levý navbar“ a navíc Multitenanci
// (docs/suplik-a-profil.md).
// Bez Reactu a bez API; testuje se vedle v library-catalog.test.ts.
import { frontendComponentItems } from "./catalog-frontend-components";
import { frontendStyleItems } from "./catalog-frontend-style";
import { frontendLogicItems } from "./catalog-frontend-logic";
import { backendItems, databaseItems } from "./catalog-backend";
import { cloudItems, cacheItems } from "./catalog-platform";
import { securityItems, testItems } from "./catalog-safety";
import { architectureItems, tenancyItems } from "./catalog-architecture";
import type { CatalogFit } from "./catalog-fit";

export type CatalogCategory =
  | "fe-components"
  | "fe-css"
  | "fe-logic"
  | "backend"
  | "database"
  | "tenancy"
  | "cloud"
  | "cache"
  | "security"
  | "tests";

/** Kategorie tak, jak ji vidí uživatel: popisek v panelu a věta, co do ní patří. */
export type CatalogCategoryInfo = { id: CatalogCategory; label: string; hint: string };

/** Pravidla položky: co musí platit a čeho se držet dál od sebe. */
export type CatalogRules = { must: string[]; mustNot: string[] };

/** Jeden krok rozpadu: dílek, směr dat nebo místo, kde bydlí stav. */
export type CatalogStep = { title: string; text: string };

export type CatalogItem = {
  id: string;
  category: CatalogCategory;
  label: string;
  hint: string;
  /** Jeden znak nebo krátká inline SVG cesta; panel ho kreslí jako značku dlaždice. */
  icon: string;
  /** `card` vytvoří při puštění kartu s bloky rozpadu, `block` jen jeden blok. Čte fáze 3. */
  kind: "card" | "block";
  rules: CatalogRules;
  decomposition: CatalogStep[];
  template: string;
  /** Pro které projekty prvek dává smysl (docs/suplik-a-profil.md); bez `fits` patří všem. */
  fits?: CatalogFit;
};

/**
 * Typ dat pro HTML5 drag&drop. Zdroj (panel) i cíl (plátno ve fázi 3) ho berou odsud,
 * aby plátno nemuselo znát panel a panel nemusel znát plátno.
 */
export const CATALOG_DRAG_TYPE = "application/x-opora-catalog-item";

export const CATALOG_CATEGORIES: CatalogCategoryInfo[] = [
  { id: "fe-components", label: "Frontend – komponenty", hint: "Rodič skládá dílky, data dolů, události nahoru." },
  { id: "fe-css", label: "Frontend – CSS a styl", hint: "Tokeny, relativní jednotky, BEM a příběhový komentář." },
  { id: "fe-logic", label: "Frontend – logika", hint: "Čisté funkce v logic/ s testem vedle, hook jen jako vazba." },
  { id: "backend", label: "Backend", hint: "Tenký router, logika v modulu prostředí, revize s CAS." },
  { id: "database", label: "Databáze", hint: "Schéma po tabulkách s vlastníkem, vratné migrace, velká data." },
  { id: "tenancy", label: "Multitenance", hint: "Víc zákazníků v jedné aplikaci: tenant v každém požadavku a oddělená data." },
  { id: "cloud", label: "Cloud a infrastruktura", hint: "Prostředí konfigurací, opakovatelný build, strukturované logy." },
  { id: "cache", label: "Cache", hint: "Klíč z digestu vstupů, invalidace při změně zdroje." },
  { id: "security", label: "Security", hint: "Same-origin zápis, validace na serveru, žádná tajemství v klientu." },
  { id: "tests", label: "Testy", hint: "Unit vedle logiky, e2e po cestě uživatele, brány hotovo." },
];

const CATEGORY_ORDER = new Map(CATALOG_CATEGORIES.map((category, index) => [category.id, index]));

/** Celý katalog v pořadí kategorií; prvky pro jednu architekturu stojí na konci své kategorie. */
export const CATALOG_ITEMS: CatalogItem[] = [
  ...frontendComponentItems,
  ...frontendStyleItems,
  ...frontendLogicItems,
  ...backendItems,
  ...databaseItems,
  ...tenancyItems,
  ...cloudItems,
  ...cacheItems,
  ...securityItems,
  ...testItems,
  ...architectureItems,
].sort((a, b) => (CATEGORY_ORDER.get(a.category) ?? 0) - (CATEGORY_ORDER.get(b.category) ?? 0));

/** Položky jedné kategorie v pořadí katalogu. */
export function itemsOf(category: CatalogCategory, items: CatalogItem[] = CATALOG_ITEMS): CatalogItem[] {
  return items.filter((item) => item.category === category);
}

/** Překlad z `dataTransfer` zpět na položku; fáze 3 dostane z tažení jen `id`. */
export function itemById(id: string, items: CatalogItem[] = CATALOG_ITEMS): CatalogItem | null {
  return items.find((item) => item.id === id) ?? null;
}

/** Rozložené háčky a čárky (U+0300–U+036F), které po `normalize("NFD")` zbydou u písmen. */
const COMBINING_MARKS = /[̀-ͯ]/g;

/** „Formulář“ a „formular“ je totéž: háčky a čárky se pro hledání zahazují. */
export function foldDiacritics(value: string): string {
  return value.normalize("NFD").replace(COMBINING_MARKS, "").toLowerCase();
}

/** Hledání nad popiskem a nápovědou; prázdný dotaz nechává katalog, jak je. */
export function searchItems(items: CatalogItem[], query: string): CatalogItem[] {
  const needle = foldDiacritics(query.trim());
  if (!needle) return items;
  return items.filter((item) => foldDiacritics(item.label + " " + item.hint).includes(needle));
}

const plural = (count: number, forms: [string, string, string]): string =>
  `${count} ${count === 1 ? forms[0] : count >= 2 && count <= 4 ? forms[1] : forms[2]}`;

/** Řádek „rozpad“ pod dlaždicí: kolik dílků a kolik pravidel položka nese. */
export function decompositionSummary(item: CatalogItem): string {
  const rules = item.rules.must.length + item.rules.mustNot.length;
  return `${plural(item.decomposition.length, ["dílek", "dílky", "dílků"])} · ${plural(rules, ["pravidlo", "pravidla", "pravidel"])}`;
}

export type CatalogViolation = {
  itemId: string;
  rule: "px" | "nesting" | "important" | "id" | "bem";
  detail: string;
};

/** px smí jen na linku, rám, obrys a stín; ikona se vejde do 24. Všechno ostatní je rem/em/%. */
const PX_ALLOWED_PROPERTY = /^(border(?!-radius)[a-z-]*|outline[a-z-]*|box-shadow|text-shadow)$/;
const ICON_LINE = /icon|ikon/i;
const MAX_ICON_PX = 24;
const MAX_NESTING = 3;
/** #id na řádku, kde selektor otevírá pravidlo (`#header {`); barvy v hodnotách (`#fff`) tam nejsou. */
const ID_SELECTOR = /#[A-Za-z_-][\w-]*/;
/** Víc než jedno `__` v jedné třídě (`.a__b__c`) už není `blok__prvek`, ale vnořený prvek v prvku. */
const DOUBLE_BEM_ELEMENT = /\.[A-Za-z_][\w-]*(?:__[\w-]+){2,}/g;

/** Šablona je stylová, když má řádek se selektorem zakončený složenou závorkou (`.blok__prvek {`). */
export function isStyleTemplate(template: string): boolean {
  return /^\s*[.#@:&[][^\n{}]*\{\s*$/m.test(template);
}

function pxViolations(item: CatalogItem): CatalogViolation[] {
  const found: CatalogViolation[] = [];
  for (const raw of item.template.split("\n")) {
    const line = raw.trim();
    const numbers = line.match(/(\d+(?:\.\d+)?)px/g);
    if (!numbers) continue;
    const property = line.includes(":") ? line.slice(0, line.indexOf(":")).trim().toLowerCase() : "";
    for (const token of numbers) {
      const value = Number(token.slice(0, -2));
      if (value === 1) continue;
      if (PX_ALLOWED_PROPERTY.test(property)) continue;
      if (ICON_LINE.test(line) && value <= MAX_ICON_PX) continue;
      found.push({ itemId: item.id, rule: "px", detail: `${token} mimo povolený seznam: ${line}` });
    }
  }
  return found;
}

/** Hloubka jednoho selektoru (bez čárky): počet dílků spojených mezerou nebo `> + ~`. */
function selectorGroupDepth(group: string): number {
  const tokens = group
    .trim()
    .replace(/[>+~]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  return tokens.length || 1;
}

/**
 * Vnoření selektorů přes tři úrovně — ať vznikne skládáním pravidel do sebe (`.a { .b { .c { .d {`)
 * nebo plochým potomkovským selektorem na jednom řádku (`.a .b .c .d {`). Obojí je stejný prohřešek:
 * čtvrtá úroveň specifičnosti, kterou pak nejde v BEM ničím přebít.
 */
function nestingViolations(item: CatalogItem): CatalogViolation[] {
  if (!isStyleTemplate(item.template)) return [];
  let depth = 0;
  let deepest = 0;
  for (const raw of item.template.split("\n")) {
    const line = raw.trim();
    // `@media`/`@container`/… otevírají blok, ale nejsou to selektory — jejich podmínka se
    // nepočítá jako dílek selektoru, jen jako obal, který zvyšuje hloubku přes { } jako dřív.
    if (/\{\s*$/.test(line) && !line.startsWith("@")) {
      const selectorText = line.slice(0, line.lastIndexOf("{"));
      const ownDepth = Math.max(...selectorText.split(",").map(selectorGroupDepth));
      deepest = Math.max(deepest, depth + ownDepth);
    }
    for (const char of line) {
      if (char === "{") deepest = Math.max(deepest, ++depth);
      else if (char === "}") depth = Math.max(0, depth - 1);
    }
  }
  return deepest > MAX_NESTING ? [{ itemId: item.id, rule: "nesting", detail: `vnoření ${deepest} úrovní` }] : [];
}

/** `!important` přebíjí kaskádu místo toho, aby ji respektoval — v katalogu na to nesmí dojít. */
function importantViolations(item: CatalogItem): CatalogViolation[] {
  if (!isStyleTemplate(item.template)) return [];
  const found: CatalogViolation[] = [];
  for (const raw of item.template.split("\n")) {
    const line = raw.trim();
    if (line.includes("!important")) {
      found.push({ itemId: item.id, rule: "important", detail: `!important: ${line}` });
    }
  }
  return found;
}

/** `#id` v selektoru váže styl na jeden konkrétní uzel stránky; BEM styluje přes třídu. */
function idSelectorViolations(item: CatalogItem): CatalogViolation[] {
  if (!isStyleTemplate(item.template)) return [];
  const found: CatalogViolation[] = [];
  for (const raw of item.template.split("\n")) {
    const line = raw.trim();
    if (!/\{\s*$/.test(line)) continue;
    const selectorText = line.slice(0, line.lastIndexOf("{"));
    if (ID_SELECTOR.test(selectorText)) {
      found.push({ itemId: item.id, rule: "id", detail: `#id selektor: ${line}` });
    }
  }
  return found;
}

/** `blok__prvek__prvek` řetězí dva prvky do sebe; BEM zná jen jednu úroveň `blok__prvek`. */
function bemViolations(item: CatalogItem): CatalogViolation[] {
  if (!isStyleTemplate(item.template)) return [];
  const matches = item.template.match(DOUBLE_BEM_ELEMENT);
  if (!matches) return [];
  return matches.map((match) => ({ itemId: item.id, rule: "bem" as const, detail: `víc než jedno __: ${match}` }));
}

/**
 * Lint pravidel z bloku 3 sektoru: běží nad katalogem v testu, aby šablony nešířily zlozvyk.
 * px jen na 1px linku, rám (mimo radius), obrys a stín, ikona do 24 — jinak rem/em/%. Selektory
 * se nevnoří přes tři úrovně, ať už skládáním pravidel do sebe nebo mezerou na jednom řádku.
 * Žádné `!important`, žádné `#id` selektory a žádná třída s víc než jedním `__` (`blok__prvek__prvek`).
 */
export function catalogLint(items: CatalogItem[] = CATALOG_ITEMS): CatalogViolation[] {
  return items.flatMap((item) => [
    ...pxViolations(item),
    ...nestingViolations(item),
    ...importantViolations(item),
    ...idSelectorViolations(item),
    ...bemViolations(item),
  ]);
}
