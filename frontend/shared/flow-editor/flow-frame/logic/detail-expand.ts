// Detail funkce (kontrakt plátna procesů §2): „Rozkreslit vnitřek“ nahradí funkci skupinou stejného jména se schématy
// funkce a výchozím řetězcem kroků vstup → krok → výstup (kroky na míru ve vrstvě funkce). Vnější hrany se přepojí na
// první a poslední krok, takže skupina splňuje pravidla K1 (souvislý řetězec, vstup jen do prvního, výstup jen z
// posledního uzlu). Ukládá rodič; tady jen vzniká nový graf.
import { specOf, type FlowGraph, type FlowGroup, type FlowNode, type NodeTypes } from "../../logic/flow-types";
import { removeNode } from "../../logic/graph-edit";
import { groupFromSelection } from "../../logic/graph-frames";
import { effectiveLayer } from "../../flow-lanes/logic/layers";

/** Typy, jejichž vnitřek jde rozkreslit. */
export const DETAIL_TYPES: readonly string[] = ["be.function", "fe.state", "transform.code", "custom.step"];
const STEPS = ["vstup", "krok", "vystup"] as const, TITLES = ["Vstup", "Krok", "Výstup"] as const, GAP = 110;

export const canExpand = (graph: FlowGraph, node: Pick<FlowNode, "id" | "type">) =>
  DETAIL_TYPES.includes(node.type) && !(graph.groups ?? []).some((group) => group.nodeIds.includes(node.id));

const isObject = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);

export function expandFunction(graph: FlowGraph, types: NodeTypes, nodeId: string): { graph: FlowGraph; group: FlowGroup } {
  const node = graph.nodes.find((item) => item.id === nodeId);
  if (!node || !canExpand(graph, node)) throw new Error("Vnitřek jde rozkreslit u funkce, stavu, kódu a kroku na míru, který není ve skupině.");
  const odd = graph.edges.find((edge) => (edge.source_node === nodeId && edge.source_port !== "main") || (edge.target_node === nodeId && edge.target_port !== "main"));
  if (odd) throw new Error(`Vazba ${odd.id} vede z jiného portu než main; rozkreslit jde jen funkce s hlavním tokem.`);
  const layer = effectiveLayer(node, specOf(types, node)) ?? "neutral", at = node.position ?? { x: 0, y: 0 };
  const title = typeof node.params?.title === "string" && node.params.title.trim() ? node.params.title.trim() : node.id;
  const rest = removeNode(graph, nodeId);
  const taken = new Set(rest.nodes.map((item) => item.id));
  const ids = STEPS.map((step) => { let id = `${nodeId}-${step}`; for (let n = 2; taken.has(id); n += 1) id = `${nodeId}-${step}-${n}`; taken.add(id); return id; });
  const steps = ids.map((id, i): FlowNode => ({ id, type: "custom.step", type_version: 1, layer, params: { title: TITLES[i], description: "" }, position: { x: at.x + i * GAP, y: at.y } }));
  const inner = ids.slice(1).map((id, i) => ({ id: `${ids[i]}-${id}`, source_node: ids[i], source_port: "main", target_node: id, target_port: "main", kind: "main" as const, label: "" }));
  const outer = graph.edges.filter((edge) => edge.source_node === nodeId || edge.target_node === nodeId)
    .map((edge) => ({ ...edge, ...(edge.target_node === nodeId ? { target_node: ids[0] } : {}), ...(edge.source_node === nodeId ? { source_node: ids[2] } : {}) }));
  const made = groupFromSelection({ ...rest, nodes: [...rest.nodes, ...steps], edges: [...rest.edges, ...inner, ...outer] }, ids, title);
  const description = typeof node.params?.description === "string" ? node.params.description.slice(0, 145) : "";
  const group: FlowGroup = { ...made.group, description, ...(isObject(node.inputSchema) ? { inputSchema: node.inputSchema } : {}), ...(isObject(node.outputSchema) ? { outputSchema: node.outputSchema } : {}) };
  return { graph: { ...made.graph, groups: (made.graph.groups ?? []).map((item) => item.id === group.id ? group : item) }, group };
}
