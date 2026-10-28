// Data Detailu prvku pro panel Studia: pracovní zadání tímtéž `useNodeSpec` jako Detail prvku (jen GET, při změně
// výběru) a karta ze sdíleného snímku agent-state (`useAgentState` sdílí jedno čtení s `useCardGuards` i plátnem,
// nic se nepolluje navíc). `item = null` (vrstva MODEL, nic vybraného) nic nečte.
import { useMemo } from "react";
import { useNodeSpec } from "@/project/architecture-editor/element-detail/logic/use-node-spec";
import { useAgentState } from "@/hub/oporahub-agent-state/logic/use-agent-state";
import { cardEntry } from "@/hub/oporahub-card-drawer/logic/card-header";
import type { NodePhase } from "@/shared/desktop-state/logic/types";
import type { Graph } from "@/shared/types/logic/types";
import type { StudioItem } from "../../logic/studio-tree";
import { elementView, type StudioElementView } from "./element-view";

export function useElementView(input: {
  project: string; workspace: string; graph: Graph; item: StudioItem | null; phase: NodePhase; done: boolean;
}): StudioElementView | null {
  const { project, workspace, graph, item, phase, done } = input;
  const nodeId = item?.node ? item.id : null;
  const spec = useNodeSpec(project, workspace, nodeId);
  const agent = useAgentState(project, workspace);
  const card = useMemo(() => (nodeId ? cardEntry(agent.state, nodeId) : null), [agent.state, nodeId]);
  return item ? elementView({ graph, item, spec, card, phase, done, now: Date.now() }) : null;
}
