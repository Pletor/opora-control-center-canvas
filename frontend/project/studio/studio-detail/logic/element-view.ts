// Obsah Detailu prvku v panelu detailu Studia (docs/studio.md §3, ve Skutečnosti jen čtení): kontext agenta, řádka
// Proč, zadání (kritéria a stav), práce a u komponenty její přímé vazby. Výpočty nepřepisuje, skládá logiku
// Detailu prvku (`element-detail/logic/*`). Čistá logika bez Reactu; `now` dodá volající.
import { agentContext, nodeLinks, type AgentContext, type NodeLink } from "@/project/architecture-editor/element-detail/logic/agent-context";
import type { SpecState } from "@/project/architecture-editor/element-detail/logic/use-node-spec";
import { whyChain, whyChainText } from "@/project/architecture-editor/element-detail/logic/why-chain";
import { workView, type WorkView } from "@/project/architecture-editor/element-detail/logic/work-view";
import type { CardEntry } from "@/hub/oporahub-card-drawer/logic/card-header";
import type { NodePhase } from "@/shared/desktop-state/logic/types";
import type { Graph } from "@/shared/types/logic/types";
import type { StudioItem } from "../../logic/studio-tree";

export type StudioElementView = {
  nodeId: string;
  context: AgentContext;
  /** Řádka „Proč“ jako text; `null` = řetěz nemá ani jeden článek. */
  why: string | null;
  spec: SpecState;
  phase: NodePhase;
  done: boolean;
  work: WorkView;
  /** Přímé vazby uzlu jen u komponenty; doména, stránka a sekce mají souhrnné vazby úrovně Studia. */
  links: { incoming: NodeLink[]; outgoing: NodeLink[] } | null;
};

/** Pohled Detailu prvku pro položku Studia; sekce (bez uzlu grafu) žádný nemá. */
export function elementView(input: {
  graph: Graph; item: StudioItem; spec: SpecState; card: CardEntry | null; phase: NodePhase; done: boolean; now: number;
}): StudioElementView | null {
  const { graph, item, spec, card, phase, done, now } = input;
  if (!item.node) return null;
  const why = whyChain(graph, item.id);
  const fields = spec.status === "ready" && spec.spec.available ? spec.spec.fields : null;
  return {
    nodeId: item.id,
    context: agentContext(graph, item.id, item.domainId ?? ""),
    why: why ? whyChainText(why) : null,
    spec, phase, done,
    work: workView(card, fields, done, now),
    links: item.kind === "component" ? nodeLinks(graph, item.id) : null,
  };
}
