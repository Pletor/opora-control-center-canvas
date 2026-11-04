// „Připraveno ke spuštění“ (setup checklist n8n): co verzi chybí, aby šla spustit. Povinný sub-port bez vazby
// (agent bez modelu), workflow bez spouštěče a uzel neznámého typu. Backend graf validuje sám; tohle je náhled pro
// člověka ještě před uložením.
import { specOf, type FlowGraph, type NodeTypes } from "./flow-types";
import { isRequired, portLabel } from "./node-role";

export type ReadinessIssue = { nodeId: string | null; text: string };

export function readinessIssues(graph: FlowGraph, types: NodeTypes): ReadinessIssue[] {
  const issues: ReadinessIssue[] = [];
  // Katalog bez spouštěčů (záměr stránky) se nespouští, spouštěč mu tedy nechybí.
  const runnable = [...types.values()].some((spec) => spec.trigger);
  if (runnable && !graph.nodes.some((node) => types.get(node.type)?.trigger)) issues.push({ nodeId: null, text: "Workflow nemá spouštěč." });
  for (const node of graph.nodes) {
    const spec = specOf(types, node);
    if (!spec) { issues.push({ nodeId: node.id, text: `${node.id}: neznámý typ ${node.type}.` }); continue; }
    for (const port of spec.ports)
      if (isRequired(port)
        && !graph.edges.some((edge) => edge.target_node === node.id && edge.target_port === port.name))
        issues.push({ nodeId: node.id, text: `${node.id}: chybí ${portLabel(port)}.` });
  }
  return issues;
}
