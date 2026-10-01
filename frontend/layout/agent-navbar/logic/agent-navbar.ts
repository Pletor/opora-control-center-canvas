// Stav sekcí Agenti a Postupy bez Reactu (docs/menu-a-katalog.md, část A): která kategorie a co se
// hledá v každé sekci zvlášť a která záložka svítí v Agentech. Jestli je sekce vidět, tu není — to
// drží menu (`layout/panel-dock/`). Stav je jeden pro celou aplikaci — neví nic o projektu,
// pracovním prostoru ani o druhu zdroje, a proto se ukládá pod jediným klíčem `opora:agent-navbar:v1`.
import { AGENT_CATEGORIES, type AgentCategory } from "@/editor/component-library/agent-catalog/logic/agent-catalog";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";

/** Dvě sekce menu nad jedním katalogem: Agenti (kdo a s jakými hranicemi) a Postupy (v jakém pořadí). */
export type AgentSection = "agents" | "flows";

/** Záložky sekce Agenti: katalog × co dostane agent vybrané karty × hook. Postupy záložky nemají. */
export type AgentNavbarTab = "catalog" | "agents" | "hook";

/** Co si každá sekce pamatuje sama: přepnutím na druhou sekci se kategorie ani hledání neztratí. */
export type AgentSectionState = { category: AgentCategory; query: string };

export type AgentNavbarState = {
  agents: AgentSectionState;
  flows: AgentSectionState;
  tab: AgentNavbarTab;
};

/** Jediný klíč pro celou aplikaci. Nikdy se do něj nepřidává id projektu. */
export const AGENT_NAVBAR_KEY = "opora:agent-navbar:v1";

export const AGENT_NAVBAR_TABS: { id: AgentNavbarTab; label: string }[] = [
  { id: "catalog", label: "Katalog" },
  { id: "agents", label: "Vybraná karta" },
  { id: "hook", label: "Hook" },
];

/** Postupy jsou workflows a pipelines; všechno ostatní v katalogu (agenti, skilly, hooky, hranice) patří Agentům. */
const FLOW_CATEGORIES: readonly string[] = ["workflows", "pipelines"];

/** Kategorie sekce v pořadí katalogu. Agenti berou zbytek, aby nová kategorie katalogu nikdy nezmizela. */
export function sectionCategories(section: AgentSection): AgentCategory[] {
  return AGENT_CATEGORIES.map((info) => info.id).filter((id) => FLOW_CATEGORIES.includes(id) === (section === "flows"));
}

/** Název sekce pro `aria-label`; píše se jednou, vedle stavu. */
export const AGENT_SECTION_TITLE: Record<AgentSection, string> = { agents: "Agenti", flows: "Postupy" };

const firstOf = (section: AgentSection): AgentCategory => sectionCategories(section)[0];

export const emptyAgentNavbar = (): AgentNavbarState => ({
  agents: { category: firstOf("agents"), query: "" },
  flows: { category: firstOf("flows"), query: "" },
  tab: "catalog",
});

/** Výběr kategorie mění jen kategorii té sekce; hledání i záložka čekají, jak je uživatel nechal. */
export const setCategory = (state: AgentNavbarState, section: AgentSection, category: AgentCategory): AgentNavbarState => ({
  ...state,
  [section]: { ...state[section], category },
});

export const setQuery = (state: AgentNavbarState, section: AgentSection, query: string): AgentNavbarState => ({
  ...state,
  [section]: { ...state[section], query },
});

export const setTab = (state: AgentNavbarState, tab: AgentNavbarTab): AgentNavbarState => ({ ...state, tab });

function parseSection(value: unknown, section: AgentSection, legacyCategory: unknown): AgentSectionState {
  const own = value && typeof value === "object" ? (value as Partial<AgentSectionState>) : {};
  const allowed = sectionCategories(section) as string[];
  const category = [own.category, legacyCategory].find((item) => typeof item === "string" && allowed.includes(item));
  return {
    category: (category as AgentCategory | undefined) ?? firstOf(section),
    query: typeof own.query === "string" ? own.query.slice(0, 120) : "",
  };
}

/**
 * Uložená preference je cizí text: co nesedí, se tiše nahradí výchozím stavem. Starší tvar nesl
 * jednu `category` pro celý panel — přejde do sekce, do které patří; starší `collapsed` se zahodí.
 */
export function parseAgentNavbar(raw: string | null): AgentNavbarState {
  const empty = emptyAgentNavbar();
  if (!raw) return empty;
  try {
    const value = JSON.parse(raw) as Record<string, unknown> | null;
    if (!value || typeof value !== "object") return empty;
    return {
      agents: parseSection(value.agents, "agents", value.category),
      flows: parseSection(value.flows, "flows", value.category),
      tab: value.tab === "agents" || value.tab === "hook" ? value.tab : "catalog",
    };
  } catch {
    return empty;
  }
}

/** Čtení preference; prohlížeč bez úložiště (soukromé okno, test) dostane výchozí stav. */
export function readState(): AgentNavbarState {
  try {
    return parseAgentNavbar(localStorage.getItem(AGENT_NAVBAR_KEY));
  } catch {
    return emptyAgentNavbar();
  }
}

/** Zápis preference nikdy neshodí panel: když úložiště není, jen se nic neuloží. */
export function writeState(state: AgentNavbarState): boolean {
  try {
    localStorage.setItem(AGENT_NAVBAR_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

/** Jen ta část události, na které pravidlo stojí — díky tomu jde přečíst i z prostého objektu v testu. */
export type ShortcutKey = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey">;

/**
 * Ctrl+Shift+. (na Macu ⌘⇧.) otevře menu na Agentech; posluchač drží `layout/panel-dock/`. Podle rozložení klávesnice přijde z téhle
 * kombinace „.“ nebo „>“, proto platí obojí. Alt drží stranou jiné zkratky plochy (Alt+1..3 přepíná
 * prostředí) a samotná tečka bez modifikátorů patří psaní.
 */
export function isCollapseShortcut(event: ShortcutKey): boolean {
  if (event.altKey) return false;
  if (!event.ctrlKey && !event.metaKey) return false;
  if (!event.shiftKey) return false;
  return event.key === "." || event.key === ">";
}

/** Skloňuje počet kroků: 1 krok / 3 kroky / 7 kroků. Sdílí ji značka i celá řádka rozpadu. */
function stepsWord(steps: number): string {
  return steps === 1 ? "krok" : steps >= 2 && steps <= 4 ? "kroky" : "kroků";
}

/** Tichá značka na řádku katalogu: jen počet kroků, bez konce — v úzkém řádku není na větu místo. */
export function stepsBadge(steps: number): string {
  return `${steps} ${stepsWord(steps)}`;
}

/**
 * Řádka pod popiskem dlaždice (tooltip, zadání karty): kolik kroků postup má a čím končí. Číslovka
 * se skloňuje stejně jako `stepsBadge` — dlaždice je čtená věta, ne tabulka.
 */
export function stepsLine(steps: number, endCriteria: string): string {
  return `${stepsBadge(steps)} · konec: ${endCriteria.trim() || "neurčen"}`;
}

/**
 * Ikony kategorií postupů podle kontraktu (`docs/panely-editoru.md`, doladění bod 4). Vrací se
 * jméno ze sady `ui-kit/icon`, ne Unicode znak: glyfy se v každém systému kreslí jinou tloušťkou a
 * leckde chybí, kdežto lineární sada drží jednu stopu napříč lištou, katalogem i zadáním karty.
 * Mapování je věc panelu (lišta i katalog musí kreslit tutéž ikonu jedním pohledem), katalog
 * (`agent-catalog.ts`) dál nese jen id, název a nápovědu kategorie.
 */
const CATEGORY_ICON: Record<AgentCategory, IconName> = {
  workflows: "workflow",
  pipelines: "link",
  rules: "scale",
  hooks: "terminal",
  skills: "sparkles",
  agents: "users",
};

/** Ikona kategorie z kontraktu; neznámá kategorie (cizí data) dostane ikonu workflows, aby lišta nikdy nezůstala prázdná. */
export function categoryIcon(category: string): IconName {
  return CATEGORY_ICON[category as AgentCategory] ?? "workflow";
}
