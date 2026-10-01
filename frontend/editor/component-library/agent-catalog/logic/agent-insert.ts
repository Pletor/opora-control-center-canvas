// Překlad položky Agentů a Postupů na to, co po puštění stojí na plátně. Hranice a role agenta jdou
// mezi pravidla karty, pipeline a hook do jejího bloku Akce a workflow do celého sektoru, kde má každá
// fáze vlastní kartu a vazbu `next` na tu další. Čisté funkce bez Reactu, bez API a bez React Flow:
// Board jen hlásí, kam se pustilo, a ukládá App.
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";
import type { DesktopState, NodeAction, NodePhase, NodeRule, NodeWorkflowFull } from "@/shared/desktop-state/logic/types";
import { emptyNodeWorkflow, NODE_PHASES } from "@/shared/desktop-state/logic/types";
import { newId, withNode } from "@/editor/workflow/blocks/logic/block-model";
import { emptyBlock, renumber } from "@/editor/node-detail/tree/logic/tree-model";
import { RELATES_BLOCK_TITLE } from "@/editor/component-library/library-catalog/logic/catalog-insert";
import { agentRelatesLines, type AgentItem } from "./agent-catalog";

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
 * Nová karta fáze vzniká rovnou ve fázi, kterou zastupuje; backend hlídá kritérii jen postup existující
 * karty. Konstanta je záložní hodnota, když krok fázi nepojmenuje.
 */
export const NEW_CARD_PHASE: NodePhase = "discover";

/** Co ze sektoru vznikne: rám postupu, karty fází v pořadí, vazby mezi nimi a stav nových karet. */
export type SectorInsert = {
  sector: CanvasNode;
  /** Karty fází v pořadí postupu; stojí uvnitř sektoru (`parentId` je jeho id). */
  children: CanvasNode[];
  /** Fáze v témže pořadí jako `children`. */
  phases: NodePhase[];
  /** Vazby `next` mezi sousedními fázemi. */
  edges: GraphEdge[];
  /** Stav Desktop v3 pro sektor i nové karty, klíč = id uzlu. */
  nodes: Record<string, NodeWorkflowFull>;
};

const stepFor = (item: AgentItem, phase: NodePhase) =>
  (item.steps ?? []).find((step) => step.title.trim().toLowerCase() === phase);

/** Fáze, které kroky workflow pojmenují, v pořadí `NODE_PHASES`. */
export function phasesFromSteps(item: AgentItem): NodePhase[] {
  return NODE_PHASES.filter((phase) => !!stepFor(item, phase));
}

/** Podstata karty fáze: text kroku se stejným názvem. */
export function phaseNote(item: AgentItem, phase: NodePhase): string {
  return stepFor(item, phase)?.text ?? "";
}

const invariantRules = (item: AgentItem): NodeRule[] =>
  item.invariants.map((rule) => ({ id: newId(), text: rule.text, kind: rule.kind }));

/**
 * Pravidla karty z položky: invarianty jako `must` / `must_not`. Role agenta (`kind: "agent"`) jde
 * první jako `must` „Role: …“ — kdo pracuje, se čte dřív než jeho hranice. Položka `info` se netáhne: `null`.
 */
export function ruleFromItem(item: AgentItem): NodeRule[] | null {
  if (item.kind === "info") return null;
  const role: NodeRule[] =
    item.kind === "agent" ? [{ id: newId(), text: `Role: ${item.label.trim()}. ${item.purpose.trim()}`, kind: "must" }] : [];
  return [...role, ...invariantRules(item)];
}

/**
 * Akce v bloku Akce: pipeline si drží identitu položky (`pipelineId`) a co se v ní má stát, nese
 * v parametrech jako texty (backend `ACTION_KEYS`, `MAX_PARAMS`). Prázdné části se vynechají.
 * Položka `info` se netáhne: `null`.
 */
export function actionFromItem(item: AgentItem): NodeAction | null {
  if (item.kind === "info") return null;
  const params: Record<string, string> = {
    purpose: item.purpose,
    steps: (item.steps ?? []).map((step) => step.title).join(" → "),
    done: (item.done ?? []).join("; "),
    stopCondition: item.stopCondition ?? "",
    relates: agentRelatesLines(item).join("; "),
  };
  return {
    id: newId(),
    pipelineId: item.id,
    label: item.label,
    params: Object.fromEntries(Object.entries(params).filter(([, value]) => value.trim())),
  };
}

/**
 * Sektor z workflow: rám se jménem a účelem postupu, uvnitř karta na každou fázi z kroků, v jedné řadě
 * a spojená vazbami `next`. Invarianty postupu jdou do pravidel sektoru (platí pro všechny fáze uvnitř,
 * `node-brief` je vydá jako `graph.parent.rules`), souvislosti do bloku „Souvisí s“ sektoru a kritéria
 * hotovo na poslední kartu. Stop podmínka nemá na kartě pole a zůstává v katalogu.
 */
export function sectorFromWorkflow(item: AgentItem, parentId: string | null, x: number, y: number): SectorInsert | null {
  if (item.kind !== "workflow") return null;
  const phases = phasesFromSteps(item);
  if (phases.length === 0) return null;
  const sector: CanvasNode = {
    id: newId(),
    parentId,
    kind: "sector",
    name: item.label,
    purpose: item.purpose,
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
  const relates = agentRelatesLines(item);
  const nodes: Record<string, NodeWorkflowFull> = {
    [sector.id]: {
      ...emptyNodeWorkflow(),
      rules: invariantRules(item),
      blocks: relates.length
        ? renumber([{ ...emptyBlock(), title: RELATES_BLOCK_TITLE, text: relates.map((line) => "- " + line).join("\n") }])
        : [],
    },
  };
  children.forEach((child, index) => {
    nodes[child.id] = {
      ...emptyNodeWorkflow(),
      phase: phases[index] ?? NEW_CARD_PHASE,
      criteria: index === last ? (item.done ?? []).map((text) => ({ id: newId(), text, checked: false })) : [],
    };
  });
  return { sector, children, phases, edges, nodes };
}

/**
 * Vložení pravidel položky do karty. Pravidlo se stejným textem, které karta už má, se přeskočí,
 * takže opakované puštění téže dlaždice kartu nezaplevelí.
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
 * Vložení akce do bloku Akce karty. Táž pipeline se nepřidá dvakrát: rozhoduje `pipelineId`, ne text.
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
