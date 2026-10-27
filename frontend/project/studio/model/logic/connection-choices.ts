// Nabídka cílů při tažení vazby z výstupu (prototyp `connectionChoices` v `model.mjs`): existující vstupy, na které
// vazba smí vést, a typy z katalogu, které by šly vytvořit a rovnou připojit. Model se nemění; samostatný Pod se nenabízí.
import { catalog, componentType } from "./catalog";
import { STUDIO_POLICY, type ConnectionPolicy } from "./connection-policy";
import { connectionError, createNode } from "./model-rules";
import type { PortRef, StudioModel } from "./model-types";

export type ExistingChoice = { nodeId: string; portId: string; name: string; type: string };
export type CreateChoice = { type: string; portId: string; name: string };

export function connectionChoices(model: Pick<StudioModel, "nodes" | "edges">, from: PortRef, query = "", policy: ConnectionPolicy = STUDIO_POLICY): { existing: ExistingChoice[]; create: CreateChoice[] } {
  const match = (value: string) => value.toLowerCase().includes(query.trim().toLowerCase());
  const existing: ExistingChoice[] = [], create: CreateChoice[] = [];
  for (const node of model.nodes)
    for (const port of componentType(node.type)?.ports ?? [])
      if (port.direction === "input" && match(`${node.name} ${port.id} ${port.type}`) && !connectionError(model, from, { nodeId: node.id, portId: port.id }, undefined, policy))
        existing.push({ nodeId: node.id, portId: port.id, name: node.name, type: node.type });
  for (const type of catalog) {
    if (type.id === "pod") continue;
    const node = createNode(type.id, undefined, "choice:" + type.id), withNode = { ...model, nodes: [...model.nodes, node] };
    for (const port of type.ports)
      if (port.direction === "input" && match(`${type.name} ${port.id} ${port.type}`) && !connectionError(withNode, from, { nodeId: node.id, portId: port.id }, undefined, policy))
        create.push({ type: type.id, portId: port.id, name: type.name });
  }
  return { existing, create };
}
