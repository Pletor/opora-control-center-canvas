// Překlad položky pravého katalogu na to, co po puštění stojí na plátně. Levý katalog nese know-how
// o kódu a dělá z něj kartu; pravý nese know-how o postupu, a ten se na plátně rozpadá na tři různé
// věci: pravidlo a role agenta jdou mezi pravidla vybrané karty, pipeline do jejího bloku Akce
// a workflow do celého sektoru, kde má každá fáze vlastní kartu a vazbu `next` na tu další.
// Čisté funkce bez Reactu, bez API a bez React Flow: Board jen hlásí, kam se pustilo, a ukládá App.
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";
import type { DesktopState, NodeAction, NodePhase, NodeRule, NodeWorkflowFull } from "@/shared/desktop-state/logic/types";
import { emptyNodeWorkflow, NODE_PHASES } from "@/shared/desktop-state/logic/types";
import { newId, withNode } from "@/editor/workflow/blocks/logic/block-model";
import type { AgentItem } from "./agent-catalog";

/** Jak se fáze uzlu jmenuje na kartě: agent čte anglické `PHASES`, člověk na plátně české jméno. */
export const PHASE_LABELS: Record<NodePhase, string> = {
  discover: "Objevit",
  define: "Definovat",
  build: "Postavit",
  verify: "Ověřit",
  live: "Provoz",
};

/** Karty fází stojí uvnitř sektoru v jedné řadě zleva doprava: první v rohu, další po 320 dál. */
export const PHASE_ORIGIN = { x: 80, y: 80 };
export const PHASE_STEP = 320;

/**
 * Nová karta fáze vzniká rovnou ve fázi, kterou zastupuje. Backend (`check_phase_transitions`
 * v backend/editor/agent_memory/desktop_v3_state.py) hlídá kritérii jen postup existující karty;
 * vznik karty v libovolné fázi je volný (změna 15. 9. 2026). Konstanta zůstává jako záložní hodnota,
 * když šablona fázi nepojmenuje.
 */
export const NEW_CARD_PHASE: NodePhase = "discover";

/** Co ze sektoru vznikne: rám postupu, karty fází v pořadí, vazby mezi nimi a stav nových karet. */
export type SectorInsert = {
  sector: CanvasNode;
  /** Karty fází v pořadí postupu; stojí uvnitř sektoru (`parentId` je jeho id). */
  children: CanvasNode[];
  /** Fáze v témže pořadí jako `children`: kterou fázi která karta zastupuje. */
  phases: NodePhase[];
  /** Vazby `next` mezi sousedními fázemi; poslední fáze už nikam nepokračuje. */
  edges: GraphEdge[];
  /** Stav Desktop v3 pro nové karty, klíč = id uzlu. */
  nodes: Record<string, NodeWorkflowFull>;
};

/** Fáze, které šablona postupu jmenuje, v pořadí `NODE_PHASES`; lint katalogu žádá u workflow všech pět. */
export function phasesFromTemplate(template: string): NodePhase[] {
  const lower = template.toLowerCase();
  return NODE_PHASES.filter((phase) => lower.includes(phase));
}

/** Podstata karty fáze: krok rozpadu se stejným názvem, jinak řádek šablony, který fázi jmenuje. */
export function phaseNote(item: AgentItem, phase: NodePhase): string {
  const step = item.decomposition.find((one) => one.title.trim().toLowerCase() === phase);
  if (step) return step.text;
  const line = item.template.split("\n").find((raw) => raw.toLowerCase().includes(phase)) ?? "";
  return line.replace(/^\s*\d+[.)]\s*/, "").trim();
}

/**
 * Pravidla uzlu z položky: každé „musí“ a „nesmí“ zvlášť, text vždy s popiskem položky vepředu, aby
 * bylo na kartě poznat, odkud pravidlo přišlo. Role agenta (`kind: "agent"`) jde první jako `must` —
 * kdo pracuje a s jakým modelem, se čte dřív než to, co má dělat. Položka `info` se netáhne: `null`.
 */
export function ruleFromItem(item: AgentItem): NodeRule[] | null {
  if (item.kind === "info") return null;
  const label = item.label.trim();
  const role: NodeRule[] =
    item.kind === "agent" ? [{ id: newId(), text: `Role: ${label}. ${item.hint.trim()}`, kind: "must" }] : [];
  return [
    ...role,
    ...item.rules.must.map((text): NodeRule => ({ id: newId(), text: `${label}: ${text}`, kind: "must" })),
    ...item.rules.mustNot.map((text): NodeRule => ({ id: newId(), text: `${label}: ${text}`, kind: "must_not" })),
  ];
}

/**
 * Akce v bloku Akce z položky: pipeline si drží identitu položky (`pipelineId`), a co se v ní má stát,
 * nese v parametrech. Parametry jsou podle backendu (`ACTION_KEYS`, `MAX_PARAMS`) objekt textů, takže
 * kroky i odkazy jdou jako jeden spojený řádek, ne jako pole. Položka `info` se netáhne: `null`.
 */
export function actionFromItem(item: AgentItem): NodeAction | null {
  if (item.kind === "info") return null;
  return {
    id: newId(),
    pipelineId: item.id,
    label: item.label,
    params: {
      steps: item.decomposition.map((step) => step.title).join(" → "),
      endCriteria: item.endCriteria,
      stopCondition: item.stopCondition,
      refs: item.refs.join(", "),
    },
  };
}

/**
 * Sektor z workflow: rám se jménem postupu a uvnitř něj karta na každou fázi, kterou šablona jmenuje,
 * v jedné řadě a spojená vazbami `next`. Kritérium konce postupu visí na poslední kartě, protože tam
 * se postup uzavírá. Pozice sektoru je surové místo puštění — o dosednutí se stará `settleCard`.
 * Jiný druh položky než `workflow` (a tedy i `info`) sektor nedá: `null`.
 */
export function sectorFromWorkflow(item: AgentItem, parentId: string | null, x: number, y: number): SectorInsert | null {
  if (item.kind !== "workflow") return null;
  const phases = phasesFromTemplate(item.template);
  if (phases.length === 0) return null;
  const sector: CanvasNode = {
    id: newId(),
    parentId,
    kind: "sector",
    name: item.label,
    purpose: item.hint,
    x: Math.round(x),
    y: Math.round(y),
  };
  const children = phases.map(
    (phase, index): CanvasNode => ({
      id: newId(),
      parentId: sector.id,
      kind: "node",
      name: PHASE_LABELS[phase],
      purpose: phaseNote(item, phase),
      x: PHASE_ORIGIN.x + index * PHASE_STEP,
      y: PHASE_ORIGIN.y,
    }),
  );
  const edges = children
    .slice(1)
    .map((child, index): GraphEdge => ({ id: newId(), source: children[index].id, target: child.id, port: "next" }));
  const last = children.length - 1;
  const nodes: Record<string, NodeWorkflowFull> = {};
  children.forEach((child, index) => {
    nodes[child.id] = {
      ...emptyNodeWorkflow(),
      phase: phases[index] ?? NEW_CARD_PHASE,
      criteria:
        index === last && item.endCriteria.trim()
          ? [{ id: newId(), text: item.endCriteria.trim(), checked: false }]
          : [],
    };
  });
  return { sector, children, phases, edges, nodes };
}

/**
 * Vložení pravidel položky do vybrané karty. Stejné pravidlo se nepřidá dvakrát: co už na kartě stojí
 * pod stejným textem, se přeskočí, takže opakované puštění téže dlaždice kartu nezaplevelí.
 */
export const insertRulesFromItem =
  (nodeId: string, item: AgentItem) =>
  (state: DesktopState): DesktopState => {
    const rules = ruleFromItem(item);
    if (!rules) return state;
    return withNode(state, nodeId, (node) => {
      const known = new Set(node.rules.map((rule) => rule.text));
      const fresh = rules.filter((rule) => !known.has(rule.text));
      return fresh.length === 0 ? node : { ...node, rules: node.rules.concat(fresh) };
    });
  };

/**
 * Vložení akce z položky do bloku Akce vybrané karty. Táž pipeline se nepřidá dvakrát: rozhoduje
 * `pipelineId`, ne text, aby se linka nerozdvojila jen proto, že se položce změnil popisek.
 */
export const insertActionFromItem =
  (nodeId: string, item: AgentItem) =>
  (state: DesktopState): DesktopState => {
    const action = actionFromItem(item);
    if (!action) return state;
    return withNode(state, nodeId, (node) =>
      node.actions.some((one) => one.pipelineId === action.pipelineId)
        ? node
        : { ...node, actions: node.actions.concat([action]) },
    );
  };
