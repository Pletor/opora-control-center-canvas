// Katalog Agentů a Postupů: JAK pracovat s modely — postupy (workflows), pipeline, agenti, skilly,
// hooky a hranice aplikace — jako data. Prvek sdílí jazyk s Knihovnou (`purpose`, `relates`,
// `invariants`, `steps`, `done`), takže model dostane stejnou orientaci, ať prvek přijde odkudkoli.
// Kontrakt: docs/menu-a-katalog.md §B3. Panel v layout/agent-navbar/ a drop na plátno (agent-insert.ts)
// berou obsah odsud a nic si nedomýšlí. Bez Reactu a bez API; test vedle v agent-catalog.test.ts.
import {
  CATALOG_ITEMS,
  foldDiacritics,
  itemById,
  relatesLines,
  relatesRef,
  type CatalogInvariant,
  type CatalogStep,
  type RelatedInfo,
} from "@/editor/component-library/library-catalog/logic/library-catalog";
import { workflowItems } from "./catalog-workflows";
import { pipelineItems } from "./catalog-pipelines";
import { boundaryItems } from "./catalog-boundaries";
import { hookItems } from "./catalog-hooks";
import { skillItems } from "./catalog-skills";
import { agentItems } from "./catalog-agents";
import type { CatalogFit } from "@/editor/component-library/library-catalog/logic/catalog-fit";

/**
 * Kategorie. `rules` je od §B3 kategorie **Hranice** (skutečné hranice aplikace); id zůstalo, aby uložené
 * preference panelu a mapování ikon platily dál.
 */
export type AgentCategory = "workflows" | "pipelines" | "agents" | "skills" | "hooks" | "rules";

/** Kategorie tak, jak ji vidí uživatel: popisek, věta co do ní patří, značka. */
export type AgentCategoryInfo = { id: AgentCategory; label: string; hint: string; icon: string };

export type AgentItem = {
  id: string;
  category: AgentCategory;
  label: string;
  /** K čemu prvek je, jedna věta. */
  purpose: string;
  /**
   * Co drop na plátno vytvoří (agent-insert.ts): `rule` → pravidlo karty, `action` → akce v bloku Akce,
   * `workflow` → sektor s kartami fází a vazbami next, `agent` → pravidlo s rolí, `info` → netáhne se.
   */
  kind: "rule" | "action" | "workflow" | "agent" | "info";
  /** S čím souvisí: `@id` prvku Knihovny nebo Agentů, nebo krátká věta. */
  relates: string[];
  /** 0–2 skutečné tvrdé hranice; na kartě se z nich stanou pravidla. */
  invariants: CatalogInvariant[];
  /** Kroky postupu; u `workflow` mají názvy fází discover/define/build/verify/live. */
  steps?: CatalogStep[];
  /** Kdy je postup u konce (1–3 ověřitelná kritéria). Povinné u workflow a pipeline. */
  done?: string[];
  /** Kdy se zastavit a vyžádat si chybějící vstup. Povinné u workflow a pipeline. */
  stopCondition?: string;
  /** Pro které projekty postup dává smysl (docs/suplik-a-profil.md); bez `fits` patří všem. */
  fits?: CatalogFit;
};

/**
 * Typ dat pro HTML5 drag&drop. Vlastní typ od Knihovny (`CATALOG_DRAG_TYPE`), aby plátno rozeznalo,
 * ze kterého katalogu puštění přišlo.
 */
export const AGENT_DRAG_TYPE = "application/x-opora-agent-item";

export const AGENT_CATEGORIES: AgentCategoryInfo[] = [
  { id: "workflows", label: "Workflows", hint: "Zadání do hotova v pěti fázích: discover → define → build → verify → live.", icon: "⟳" },
  { id: "pipelines", label: "Pipelines", hint: "Řetěz kroků do bloku Akce, odkazuje na prvky Knihovny.", icon: "⇶" },
  { id: "agents", label: "Agenti", hint: "Role a model: hlavní vlákno, Explore, Sonnet, Opus.", icon: "◉" },
  { id: "skills", label: "Skills", hint: "Kdy sáhnout po instalovaném skillu.", icon: "✺" },
  { id: "hooks", label: "Hooky a commands", hint: "Restart serveru a to, co aplikace čte z Claude Code.", icon: "⎇" },
  { id: "rules", label: "Hranice", hint: "Skutečné hranice aplikace; na kartu se táhnou jako pravidlo.", icon: "⚖" },
];

export const AGENT_ITEMS: AgentItem[] = [
  ...workflowItems,
  ...pipelineItems,
  ...agentItems,
  ...skillItems,
  ...hookItems,
  ...boundaryItems,
];

/** Položky jedné kategorie v pořadí katalogu. */
export function agentItemsOf(category: AgentCategory, items: AgentItem[] = AGENT_ITEMS): AgentItem[] {
  return items.filter((item) => item.category === category);
}

/** Překlad z `dataTransfer` zpět na položku; drop dostane z tažení jen `id`. */
export function agentItemById(id: string, items: AgentItem[] = AGENT_ITEMS): AgentItem | null {
  return items.find((item) => item.id === id) ?? null;
}

/** `@id` se hledá v Agentech i v Knihovně: postup smí odkázat na prvek kódu i na jiný postup. */
export function relatedInfo(id: string): RelatedInfo | null {
  return agentItemById(id) ?? itemById(id);
}

/** Řádky „Souvisí s“ položky, `@id` přeložené na „Název: účel“. */
export function agentRelatesLines(item: AgentItem): string[] {
  return relatesLines(item.relates, relatedInfo);
}

/** Hledání nad popiskem a účelem, bez ohledu na diakritiku; prázdný dotaz nechává katalog, jak je. */
export function searchAgentItems(items: AgentItem[], query: string): AgentItem[] {
  const needle = foldDiacritics(query.trim());
  if (!needle) return items;
  return items.filter((item) => foldDiacritics(item.label + " " + item.purpose).includes(needle));
}

export type AgentCatalogViolation = {
  itemId: string;
  rule: "purpose" | "done" | "stop" | "steps" | "phases" | "ref" | "invariants";
  detail: string;
};

/** Fáze uzlu (`PHASES` v backend/editor/agent_memory/desktop_v3_state.py), které musí pojmenovat kroky workflow. */
const WORKFLOW_PHASES = ["discover", "define", "build", "verify", "live"] as const;

/**
 * Lint kontraktu §B3: každá položka má účel a nejvýš 2 invarianty; postup a pipeline mají kroky, 1–3
 * kritéria hotovo a stop podmínku; kroky workflow pojmenují všech pět fází uzlu; každé `@id`
 * v `relates` míří na existující prvek Agentů nebo Knihovny a pipeline odkazuje aspoň na jeden prvek Knihovny.
 */
export function agentCatalogLint(items: AgentItem[] = AGENT_ITEMS): AgentCatalogViolation[] {
  const library = new Set(CATALOG_ITEMS.map((item) => item.id));
  const known = new Set([...library, ...items.map((item) => item.id)]);
  const found: AgentCatalogViolation[] = [];
  const add = (item: AgentItem, rule: AgentCatalogViolation["rule"], detail: string) => found.push({ itemId: item.id, rule, detail });
  for (const item of items) {
    if (!item.purpose.trim()) add(item, "purpose", "Chybí účel (purpose).");
    if (item.invariants.length > 2) add(item, "invariants", `Invariant je ${item.invariants.length}, smí být 0–2.`);
    if (item.kind === "workflow" || item.category === "pipelines") {
      const done = item.done ?? [];
      if (done.length < 1 || done.length > 3) add(item, "done", `Kritérií hotovo je ${done.length}, smí být 1–3.`);
      if (!item.stopCondition?.trim()) add(item, "stop", "Chybí stop podmínka (stopCondition).");
      if (!item.steps?.length) add(item, "steps", "Chybí kroky (steps).");
    }
    if (item.kind === "workflow") {
      const titles = new Set((item.steps ?? []).map((step) => step.title.trim().toLowerCase()));
      const missing = WORKFLOW_PHASES.filter((phase) => !titles.has(phase));
      if (missing.length) add(item, "phases", `Kroky workflow postrádají fáze: ${missing.join(", ")}.`);
    }
    const refs = item.relates.filter((line) => line.trim().startsWith("@"));
    for (const line of refs) {
      const ref = relatesRef(line);
      if (!ref || !known.has(ref) || ref === item.id) add(item, "ref", `Neznámý odkaz: ${line}.`);
    }
    if (item.category === "pipelines" && !refs.some((line) => library.has(relatesRef(line) ?? ""))) {
      add(item, "ref", "Pipeline neodkazuje na žádný prvek Knihovny.");
    }
  }
  return found;
}

/**
 * Zdroj tažení: do schránky tažení jde jen id položky pod typem `AGENT_DRAG_TYPE`.
 * Cíl (plátno) si položku dohledá přes `agentItemById`; panel o plátně nic neví.
 */
export function startAgentDrag(dataTransfer: DataTransfer, itemId: string): void {
  dataTransfer.setData(AGENT_DRAG_TYPE, itemId);
  dataTransfer.effectAllowed = "copy";
}
