// Jednorázový index grafu a stavu pro přestavbu plátna. Board ho staví jednou za změnu grafu nebo stavu
// (`useMemo([graph, state])`) a karty z něj čtou místo procházení všech uzlů, hran, pravidel a rozhodnutí
// pro každou kartu zvlášť. Výstupy funkcí s indexem a bez něj jsou stejné (board-index.test.ts).
import type { CanvasNode, Graph, GraphEdge } from "@/shared/types/logic/types";
import type { Decision, DesktopState, Rule } from "@/shared/desktop-state/logic/types";

/** Pravidlo projektu s pozicí v `state.rules`, aby indexovaný výpočet zachoval původní pořadí řádků. */
export type RuleSlot = { rule: Rule; position: number };

export type BoardIndex = {
  /** Uzel podle id; při duplicitním id vyhrává první (jako `graph.nodes.find`). */
  byId: ReadonlyMap<string, CanvasNode>;
  /** Druh uzlu podle id pro obálku předávky na vazbách (jako `new Map(nodes.map(...))`). */
  kinds: ReadonlyMap<string, CanvasNode["kind"]>;
  /** Přímé děti podle rodiče v pořadí grafu (kořen vrstvy = `null`). */
  children: ReadonlyMap<string | null, CanvasNode[]>;
  /** Příchozí vazby podle cíle bez toku oblastí (`flow`), v pořadí grafu. */
  incoming: ReadonlyMap<string, GraphEdge[]>;
  /** Rozhodnutí podle uzlu v pořadí stavu. */
  decisionsByNode: ReadonlyMap<string, Decision[]>;
  /** Id rozhodnutí, která nahradilo jiné rozhodnutí (`supersedes`). */
  superseded: ReadonlySet<string>;
  /** Pravidla projektu s rozsahem `node` podle cíle, v pořadí stavu (stejná pole pro kartu i dědění). */
  nodeRules: ReadonlyMap<string, Rule[]>;
  /** Pravidla rozsahu `node` s pozicí podle cíle. */
  nodeRuleSlots: ReadonlyMap<string, RuleSlot[]>;
  /** Pravidla rozsahu `project` a `path` s pozicí. */
  generalRuleSlots: readonly RuleSlot[];
};

const push = <K, V>(map: Map<K, V[]>, key: K, value: V) => {
  const list = map.get(key);
  if (list) list.push(value);
  else map.set(key, [value]);
};

export function buildBoardIndex(graph: Graph, state: DesktopState): BoardIndex {
  const byId = new Map<string, CanvasNode>();
  const kinds = new Map<string, CanvasNode["kind"]>();
  const children = new Map<string | null, CanvasNode[]>();
  for (const node of graph.nodes) {
    if (!byId.has(node.id)) byId.set(node.id, node);
    kinds.set(node.id, node.kind);
    push(children, node.parentId, node);
  }
  const incoming = new Map<string, GraphEdge[]>();
  for (const edge of graph.edges) if (edge.port !== "flow") push(incoming, edge.target, edge);
  const decisionsByNode = new Map<string, Decision[]>();
  const superseded = new Set<string>();
  for (const decision of state.decisions) {
    push(decisionsByNode, decision.nodeId, decision);
    if (decision.supersedes) superseded.add(decision.supersedes);
  }
  const nodeRules = new Map<string, Rule[]>();
  const nodeRuleSlots = new Map<string, RuleSlot[]>();
  const generalRuleSlots: RuleSlot[] = [];
  state.rules.forEach((rule, position) => {
    if (rule.scope === "node") {
      push(nodeRules, rule.target, rule);
      push(nodeRuleSlots, rule.target, { rule, position });
    } else generalRuleSlots.push({ rule, position });
  });
  return { byId, kinds, children, incoming, decisionsByNode, superseded, nodeRules, nodeRuleSlots, generalRuleSlots };
}

/** Počet přímých dětí uzlu (jako `graph.nodes.filter(c => c.parentId === id).length`). */
export const childCount = (index: BoardIndex, id: string) => index.children.get(id)?.length ?? 0;

const NO_RULES: Rule[] = [];
/** Pravidla projektu zapsaná přímo na kartu (jako `state.rules.filter(scope node && target id)`). */
export const ownNodeRules = (index: BoardIndex, id: string) => index.nodeRules.get(id) ?? NO_RULES;
