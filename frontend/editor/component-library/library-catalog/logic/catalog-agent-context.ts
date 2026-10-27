// Přesný kontext pro agenta na položce Knihovny (docs/zive-zobrazeni-a-knihovna.md §5): technologie, stavy, porty,
// co si agent stáhne (`fetch`) a co vyplní (`fill`). Všechna pole jsou volitelná; tady je jejich tvar a lint.
// Vložení je skládá do karty bez modelu (catalog-plan.ts). Bez Reactu a bez API; test vedle.
import { EDGE_CARRIES, type EdgeCarries } from "@/shared/types/logic/types";

/** Port položky: kudy do karty tok vchází (`in`) nebo z ní vychází (`out`) a co po vazbě teče. */
export type CatalogPort = { id: string; direction: "in" | "out"; carries: EdgeCarries };

/** Co si agent stáhne do kontextu: soubory a dokumenty jako relativní cesty v repozitáři (dokument i `https://`). */
export type CatalogFetch = { files: string[]; docs: string[] };

/**
 * Pole karty, která agent opravdu umí zapsat (a smí tedy stát ve `fill`): `purpose` a `sourceRef` změnou grafu
 * v OporaHubu, `spec.*` a `text` přes `extend` dávky plánu s revizí, `card.tech` / `card.states` / `card.section`,
 * `blocks` a `rules` přes `extend`. Zrcadlí `CARD_FILL_FIELDS` v `backend/canvas/card_agent_context.py`.
 */
export const CARD_FILL_FIELDS = [
  "purpose", "sourceRef", "spec.goal", "spec.non_goals", "spec.acceptance", "text",
  "card.tech", "card.states", "card.section", "blocks", "rules",
] as const;
export type CardFillField = (typeof CARD_FILL_FIELDS)[number];

/** Stavy chyby jako `ERROR_STATES` v `backend/project/architecture/map_check.py` (bez ohledu na velikost a okraje). */
export const ERROR_STATES = ["chyba", "error", "selhání"] as const;

export const TECH_MAX = 80;
export const STATES_MAX = 8;
export const STATE_MAX = 40;
export const PORTS_MAX = 8;
export const FETCH_ITEMS_MAX = 20;
export const FETCH_PATH_MAX = 200;
const PORT_ID = /^[A-Za-z0-9_-]{1,40}$/;
/** Relativní cesta v repozitáři: dílky bez `.`, `..`, `.git`, zpětného lomítka a znaků, které Windows nepřijme. */
const REPO_PATH = /^(?!\/)(?:[^/\\:*?"<>|\u0000-\u001f]+\/)*[^/\\:*?"<>|\u0000-\u001f]+$/;
const HTTPS_URL = /^https:\/\/\S{1,192}$/;

/** Shoda s kartou (`card_text` v backend/canvas/graph.py): neprázdný, bez okrajových mezer a řídicích znaků. */
export function cardText(value: string, limit: number): boolean {
  return value.length > 0 && value.length <= limit && value === value.trim() && !/[\u0000-\u001f\u007f-\u009f]/.test(value);
}

/** Relativní cesta v repozitáři do 200 znaků, bez `..`, `.git` a úvodního lomítka. */
export function isRepoPath(value: string): boolean {
  if (!REPO_PATH.test(value) || value.length > FETCH_PATH_MAX) return false;
  return value.split("/").every((part) => part !== "." && part !== ".." && part.toLowerCase() !== ".git" && !/[. ]$/.test(part));
}

/** Má seznam stavů stav chyby? Stejné pravidlo jako `state.no-error` kontroly mapy. */
export function hasErrorState(states: readonly string[]): boolean {
  return states.some((state) => (ERROR_STATES as readonly string[]).includes(state.trim().toLowerCase()));
}

export type AgentContextRule = "tech" | "states" | "ports" | "fetch" | "fill";
export type AgentContextItem = {
  id: string; tech?: string; states?: string[]; ports?: CatalogPort[]; fetch?: CatalogFetch; fill?: string[];
};
export type AgentContextViolation = { itemId: string; rule: AgentContextRule; detail: string };

function fetchViolations(item: AgentContextItem, exists?: (path: string) => boolean): string[] {
  const found: string[] = [];
  for (const key of ["files", "docs"] as const) {
    const list = item.fetch?.[key] ?? [];
    if (list.length > FETCH_ITEMS_MAX) found.push(`fetch.${key} má ${list.length} položek, smí nejvýš ${FETCH_ITEMS_MAX}.`);
    if (new Set(list).size !== list.length) found.push(`fetch.${key} má duplicitní položku.`);
    for (const path of list) {
      const url = key === "docs" && HTTPS_URL.test(path);
      if (!url && !isRepoPath(path)) found.push(`fetch.${key}: neplatná relativní cesta ${path}.`);
      else if (!url && exists && !exists(path)) found.push(`fetch.${key}: soubor ${path} v repozitáři neexistuje.`);
    }
  }
  return found;
}

/**
 * Lint kontextu pro agenta: `tech` 1–80 znaků, `states` 1–8 různých stavů po 1–40 znacích, u položky s výstupním
 * portem `command` povinně stav chyby, porty s unikátním id a známým `carries`, `fetch` jako relativní cesty
 * (existenci ověří `exists`, když ho volající má – test nad repozitářem), `fill` jen z `CARD_FILL_FIELDS`.
 */
export function agentContextViolations(item: AgentContextItem, exists?: (path: string) => boolean): AgentContextViolation[] {
  const found: AgentContextViolation[] = [];
  const add = (rule: AgentContextRule, detail: string) => found.push({ itemId: item.id, rule, detail });
  if (item.tech !== undefined && !cardText(item.tech, TECH_MAX)) add("tech", `tech musí mít 1–${TECH_MAX} znaků bez okrajových mezer.`);
  const states = item.states;
  if (states !== undefined) {
    if (states.length < 1 || states.length > STATES_MAX) add("states", `Stavů je ${states.length}, smí být 1–${STATES_MAX}.`);
    if (!states.every((state) => cardText(state, STATE_MAX))) add("states", `Stav má 1–${STATE_MAX} znaků bez okrajových mezer.`);
    if (new Set(states.map((state) => state.toLowerCase())).size !== states.length) add("states", "Stavy se opakují.");
  }
  const ports = item.ports ?? [];
  if (ports.length > PORTS_MAX) add("ports", `Portů je ${ports.length}, smí nejvýš ${PORTS_MAX}.`);
  if (new Set(ports.map((port) => port.id)).size !== ports.length) add("ports", "Id portů se opakují.");
  for (const port of ports) {
    if (!PORT_ID.test(port.id)) add("ports", `Neplatné id portu ${port.id}.`);
    if (port.direction !== "in" && port.direction !== "out") add("ports", `Port ${port.id}: směr je in nebo out.`);
    if (!EDGE_CARRIES.includes(port.carries)) add("ports", `Port ${port.id}: neznámý druh toku ${port.carries}.`);
  }
  if (ports.some((port) => port.direction === "out" && port.carries === "command") && !hasErrorState(states ?? [])) {
    add("states", "Položka odesílá (výstupní port command), ale nemá stav chyby (chyba / error / selhání).");
  }
  for (const detail of fetchViolations(item, exists)) add("fetch", detail);
  const fill = item.fill;
  if (fill !== undefined) {
    if (fill.length < 1) add("fill", "fill je prázdný; bez děr pole vynechte.");
    if (new Set(fill).size !== fill.length) add("fill", "fill má duplicitní pole.");
    for (const field of fill) if (!(CARD_FILL_FIELDS as readonly string[]).includes(field)) add("fill", `Pole ${field} agent vyplnit neumí.`);
  }
  return found;
}
