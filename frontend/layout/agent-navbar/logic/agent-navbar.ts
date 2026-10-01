// Stav panelu Agenti a postupy bez Reactu: která kategorie, co se hledá a která záložka. Jestli je
// panel vidět, tu není — to drží šuplík (`layout/panel-dock/`) jen v paměti sezení. Panel je jeden pro celou aplikaci — neví nic o projektu, pracovním prostoru ani
// o druhu zdroje, a proto se ukládá pod jediným klíčem `opora:agent-navbar:v1`.
import { AGENT_CATEGORIES, type AgentCategory } from "@/editor/component-library/agent-catalog/logic/agent-catalog";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";

/** Záložky v hlavě rozbaleného panelu: knihovna postupů × co dostane agent vybrané karty. */
export type AgentNavbarTab = "catalog" | "agents" | "hook";

export type AgentNavbarState = {
  /** Vybraná kategorie katalogu; nikdy `null`, protože lišta i katalog vždy něco ukazují. */
  category: AgentCategory;
  query: string;
  tab: AgentNavbarTab;
};

/** Jediný klíč pro celou aplikaci. Nikdy se do něj nepřidává id projektu. */
export const AGENT_NAVBAR_KEY = "opora:agent-navbar:v1";

export const AGENT_NAVBAR_TABS: { id: AgentNavbarTab; label: string }[] = [
  { id: "catalog", label: "Katalog" },
  { id: "agents", label: "Agenti" },
  { id: "hook", label: "Hook" },
];

/** Název police. Je i v `aria-label`, proto stojí vedle stavu, ne v komponentě — píše se jednou. */
export const AGENT_NAVBAR_TITLE = "Agenti a postupy";

export const emptyAgentNavbar = (): AgentNavbarState => ({
  category: "workflows",
  query: "",
  tab: "catalog",
});

/** Výběr kategorie mění jen kategorii; hledání i záložka čekají, jak je uživatel nechal. */
export const setCategory = (state: AgentNavbarState, category: AgentCategory): AgentNavbarState => ({
  ...state,
  category,
});

export const setQuery = (state: AgentNavbarState, query: string): AgentNavbarState => ({ ...state, query });
export const setTab = (state: AgentNavbarState, tab: AgentNavbarTab): AgentNavbarState => ({ ...state, tab });

const KNOWN = new Set<string>(AGENT_CATEGORIES.map((category) => category.id));

/** Uložená preference je cizí text: co nesedí, se tiše nahradí výchozím stavem. */
export function parseAgentNavbar(raw: string | null): AgentNavbarState {
  const empty = emptyAgentNavbar();
  if (!raw) return empty;
  try {
    const value = JSON.parse(raw) as Partial<AgentNavbarState> | null;
    if (!value || typeof value !== "object") return empty;
    return {
      // Starší preference nesla `collapsed`. Panel se dnes otevírá jen v šuplíku a po načtení
      // stránky je vždy zavřený, proto se uložená hodnota při čtení zahodí.
      category: typeof value.category === "string" && KNOWN.has(value.category) ? (value.category as AgentCategory) : empty.category,
      query: typeof value.query === "string" ? value.query.slice(0, 120) : "",
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
 * Ctrl+Shift+. (na Macu ⌘⇧.) otevře a zavře panel; posluchač drží `layout/panel-dock/`. Podle rozložení klávesnice přijde z téhle
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
