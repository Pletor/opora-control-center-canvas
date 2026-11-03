// Výřez registru a grafu srdce pro testy logiky (tvar `GET /api/flow/node-types` a seedu „Srdce v1“).
import { nodeTypeMap, type FlowGraph, type NodeTypeSpec, type PortSpec } from "./flow-types";

const port = (name: string, direction: "in" | "out", kind: PortSpec["kind"] = "main", cardinality: PortSpec["cardinality"] = "many"): PortSpec =>
  ({ name, direction, kind, cardinality });
const step = [port("main", "in"), port("main", "out")];

export const FIXTURE_TYPES: NodeTypeSpec[] = [
  { type: "trigger.manual", version: 1, trigger: true, ports: [port("main", "out")] },
  { type: "trigger.heart_event", version: 1, trigger: true, ports: [port("main", "out"), port("empty", "out")] },
  { type: "decision.jev", version: 1, trigger: false, ports: step },
  { type: "context.snapshot", version: 1, trigger: false, ports: step },
  { type: "agent.claude", version: 1, trigger: false,
    ports: [...step, port("model", "in", "model", "one"), port("tool", "in", "tool"), port("memory", "in", "memory", "one")] },
  { type: "model.claude", version: 1, trigger: false, ports: [port("model", "out", "model")] },
  { type: "tool.opora_heart", version: 1, trigger: false, ports: [port("tool", "out", "tool")] },
  { type: "approval.human", version: 1, trigger: false, ports: [port("main", "in"), port("approved", "out"), port("rejected", "out"), port("timeout", "out")] },
];
export const TYPES = nodeTypeMap(FIXTURE_TYPES);

export function heartGraph(): FlowGraph {
  const node = (id: string, type: string, x: number, y: number, params: Record<string, unknown> = {}) => ({ id, type, type_version: 1, params, position: { x, y } });
  const edge = (id: string, source: string, target: string, kind: PortSpec["kind"] = "main") =>
    ({ id, source_node: source, source_port: kind, target_node: target, target_port: kind, kind, label: "" });
  return {
    nodes: [node("udalost", "trigger.heart_event", 0, 0), node("jev", "decision.jev", 260, 0), node("srdce", "agent.claude", 520, 0, { per_hour: 6 }),
      node("model", "model.claude", 480, 200, { model: "haiku" })],
    edges: [edge("udalost-jev", "udalost", "jev"), edge("jev-srdce", "jev", "srdce"), edge("model-srdce", "model", "srdce", "model")],
  };
}
