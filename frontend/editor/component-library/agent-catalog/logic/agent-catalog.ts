// Katalog pravého navbaru: JAK ovládat Clauda a agenty — Workflows, Pipelines, Pravidla, Hooky
// a commands, Skills, Agenti — jako data. Položka sdílí tvar s levým navbarem (rules, decomposition,
// template z library-catalog, `foldDiacritics` a `CatalogRules`/`CatalogStep` odsud, ne kopie), navíc
// nese `endCriteria` a `stopCondition`, protože tady je `template` postup (číslovaný text), ne kostra
// kódu. Panel v layout/agent-navbar/ a drop na plátno (agent-insert.ts, fáze 3 sektoru) berou obsah
// odsud a nic si nedomýšlí. Bez Reactu a bez API; test vedle v agent-catalog.test.ts.
import {
  CATALOG_ITEMS,
  foldDiacritics,
  type CatalogRules,
  type CatalogStep,
} from "@/editor/component-library/library-catalog/logic/library-catalog";
import { workflowItems } from "./catalog-workflows";
import { pipelineItems } from "./catalog-pipelines";
import { ruleItems } from "./catalog-rules";
import { hookItems } from "./catalog-hooks";
import { skillItems } from "./catalog-skills";
import { agentItems } from "./catalog-agents";

export type AgentCategory = "workflows" | "pipelines" | "rules" | "hooks" | "skills" | "agents";

/** Kategorie tak, jak ji vidí uživatel v pravém navbaru: popisek, věta co do ní patří, značka. */
export type AgentCategoryInfo = { id: AgentCategory; label: string; hint: string; icon: string };

export type AgentItem = {
  id: string;
  category: AgentCategory;
  label: string;
  hint: string;
  /** Jeden znak nebo krátká inline SVG cesta; panel ho kreslí jako značku dlaždice. */
  icon: string;
  /**
   * Co drop na plátno vytvoří (fáze 3 sektoru, agent-insert.ts): `rule` → pravidlo uzlu,
   * `action` → akce v bloku Akce, `workflow` → sektor s uzly podle fází a vazbami next,
   * `agent` → pravidlo uzlu s rolí a modelem, `info` → nedá se přetáhnout.
   */
  kind: "rule" | "action" | "workflow" | "agent" | "info";
  rules: CatalogRules;
  decomposition: CatalogStep[];
  /** Postup jako číslovaný text (ne kostra kódu); u kind "workflow" musí jmenovat fáze discover/define/build/verify/live. */
  template: string;
  /** Kdy je postup u konce — podle čeho pozná agent i člověk úspěšný konec. */
  endCriteria: string;
  /** Kdy se má zastavit a vyžádat si chybějící vstup, místo aby domýšlel. */
  stopCondition: string;
  /** Id položek levého katalogu (`CATALOG_ITEMS`), na které krok pipeline odkazuje — odkazem, ne kopií. Smí být prázdné. */
  refs: string[];
};

/**
 * Typ dat pro HTML5 drag&drop pravého navbaru. Vlastní typ od levého katalogu (`CATALOG_DRAG_TYPE`),
 * aby plátno rozeznalo, ze kterého navbaru puštění přišlo.
 */
export const AGENT_DRAG_TYPE = "application/x-opora-agent-item";

export const AGENT_CATEGORIES: AgentCategoryInfo[] = [
  { id: "workflows", label: "Workflows", hint: "Zadání do hotova v pěti fázích: discover → define → build → verify → live.", icon: "⟳" },
  { id: "pipelines", label: "Pipelines", hint: "Řetěz kroků, které odkazují na know-how z levé knihovny.", icon: "⇶" },
  { id: "rules", label: "Pravidla", hint: "Musí / nesmí z CLAUDE.md a z kontraktu karty pro agenty.", icon: "⚖" },
  { id: "hooks", label: "Hooky a commands", hint: "Ověřovací příkazy, restart serveru, Claude Code hooky a commands.", icon: "⎇" },
  { id: "skills", label: "Skills", hint: "Kdy sáhnout po instalovaném skillu — podle jeho popisu, ne názvu.", icon: "✺" },
  { id: "agents", label: "Agenti", hint: "Role a model: hlavní vlákno, Explore, Sonnet, Opus.", icon: "◉" },
];

export const AGENT_ITEMS: AgentItem[] = [
  ...workflowItems,
  ...pipelineItems,
  ...ruleItems,
  ...hookItems,
  ...skillItems,
  ...agentItems,
];

/** Položky jedné kategorie v pořadí katalogu. */
export function agentItemsOf(category: AgentCategory, items: AgentItem[] = AGENT_ITEMS): AgentItem[] {
  return items.filter((item) => item.category === category);
}

/** Překlad z `dataTransfer` zpět na položku; fáze 3 dostane z tažení jen `id`. */
export function agentItemById(id: string, items: AgentItem[] = AGENT_ITEMS): AgentItem | null {
  return items.find((item) => item.id === id) ?? null;
}

/** Hledání nad popiskem a nápovědou, bez ohledu na diakritiku; prázdný dotaz nechává katalog, jak je. */
export function searchAgentItems(items: AgentItem[], query: string): AgentItem[] {
  const needle = foldDiacritics(query.trim());
  if (!needle) return items;
  return items.filter((item) => foldDiacritics(item.label + " " + item.hint).includes(needle));
}

export type AgentCatalogViolation = {
  itemId: string;
  rule: "end" | "stop" | "ref" | "template";
  detail: string;
};

/** Fáze uzlu (`PHASES` v backend/editor/agent_memory/desktop_v3_state.py), které musí jmenovat každý workflow. */
const WORKFLOW_PHASES = ["discover", "define", "build", "verify", "live"] as const;

/**
 * Lint kontraktu karty pro agenty: každá položka musí nést kritérium konce a stop podmínku (jinak
 * agent neví, kdy skončit ani kdy se zeptat), každý `refs` musí mířit na existující položku levého
 * katalogu, šablona nesmí být prázdná a workflow musí jmenovat všech pět fází uzlu.
 */
export function agentCatalogLint(items: AgentItem[] = AGENT_ITEMS): AgentCatalogViolation[] {
  const knownRefs = new Set(CATALOG_ITEMS.map((item) => item.id));
  const found: AgentCatalogViolation[] = [];
  for (const item of items) {
    if (!item.endCriteria.trim()) {
      found.push({ itemId: item.id, rule: "end", detail: "Chybí kritérium konce (endCriteria)." });
    }
    if (!item.stopCondition.trim()) {
      found.push({ itemId: item.id, rule: "stop", detail: "Chybí stop podmínka (stopCondition)." });
    }
    if (!item.template.trim()) {
      found.push({ itemId: item.id, rule: "template", detail: "Chybí šablona postupu (template)." });
    } else if (item.kind === "workflow") {
      const lower = item.template.toLowerCase();
      const missing = WORKFLOW_PHASES.filter((phase) => !lower.includes(phase));
      if (missing.length > 0) {
        found.push({ itemId: item.id, rule: "template", detail: `Šablona workflow postrádá fáze: ${missing.join(", ")}.` });
      }
    }
    for (const ref of item.refs) {
      if (!knownRefs.has(ref)) {
        found.push({ itemId: item.id, rule: "ref", detail: `Neznámý odkaz na levý katalog: ${ref}.` });
      }
    }
  }
  return found;
}

/**
 * Zdroj tažení pravého navbaru: do schránky tažení jde jen id položky pod typem `AGENT_DRAG_TYPE`.
 * Cíl (plátno, fáze 3) si položku dohledá přes `agentItemById`; panel o plátně nic neví.
 */
export function startAgentDrag(dataTransfer: DataTransfer, itemId: string): void {
  dataTransfer.setData(AGENT_DRAG_TYPE, itemId);
  dataTransfer.effectAllowed = "copy";
}
