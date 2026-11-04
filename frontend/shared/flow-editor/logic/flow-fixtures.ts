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

// Výřez katalogu toků dat knihovny (`GET /api/flow/node-types?kind=library_flow`): kategorie, povinné porty s popiskem
// a vektorové úložiště s variantou „nástroj pro agenta“.
const sub = (kind: PortSpec["kind"], direction: "in" | "out", required = false, cardinality: PortSpec["cardinality"] = "one"): PortSpec =>
  ({ name: kind, direction, kind, cardinality, required, label: kind });
export const LIBRARY_TYPES: NodeTypeSpec[] = [
  { type: "trigger.chat", version: 1, trigger: true, category: "trigger", ports: [port("main", "out")] },
  { type: "ai.agent", version: 1, trigger: false, category: "ai", dynamicPorts: true,
    ports: [port("main", "in"), { ...sub("model", "in", true), label: "Model" }, sub("memory", "in"), sub("tool", "in", false, "many"), port("main", "out")] },
  { type: "ai.model", version: 1, trigger: false, category: "ai", ports: [sub("model", "out")] },
  { type: "ai.vectorStore", version: 1, trigger: false, category: "ai", dynamicPorts: true, params: { mode: "insert | retrieveAsTool" },
    ports: [port("main", "in"), sub("embedding", "in", true), sub("document", "in", true), port("main", "out")],
    variants: [{ params: { mode: "retrieveAsTool" }, ports: [sub("embedding", "in", true), sub("tool", "out")] }] },
  { type: "ai.documentLoader", version: 1, trigger: false, category: "ai", ports: [sub("textSplitter", "in"), sub("document", "out")] },
  { type: "transform.set", version: 1, trigger: false, category: "transform", ports: step },
  { type: "flow.if", version: 1, trigger: false, category: "flow", ports: [port("main", "in"), port("true", "out"), port("false", "out")] },
];
export const LIBRARY = nodeTypeMap(LIBRARY_TYPES);

/** Výřez katalogu plátna procesů (vrstvy, `use` / `avoid`, `intents`) a ukázkový případ „Uložit BMI“ s uzly všech vrstev. */
const typed = (type: string, layer: NodeTypeSpec["layer"], intents: string[], use: string, avoid: string, trigger = false): NodeTypeSpec =>
  ({ type, version: 1, trigger, layer, intents, use, avoid, ports: trigger ? [port("main", "out")] : step });
const DATA_KINDS_OF: Record<string, Pick<NodeTypeSpec, "accepts" | "emits">> = {
  "fe.form": { emits: "json" }, "be.endpoint": { accepts: ["json", "text"], emits: "json" }, "be.validate": { accepts: ["json"], emits: "json" },
  "be.function": { accepts: ["json", "number"], emits: "number" }, "db.write": { accepts: ["number", "json", "table"], emits: "table" }, "fe.notify": { accepts: ["text", "event", "json"] },
};
export const PROCESS_TYPES: NodeTypeSpec[] = ([
  typed("trigger.manual", "neutral", ["input"], "proces začíná ručně", "má začít událost", true),
  typed("fe.form", "fe", ["input"], "uživatel zadává hodnoty do formuláře", "hodnoty přicházejí ze serveru"),
  typed("fe.click", "fe", ["input", "show"], "uživatel spouští akci tlačítkem", "akce běží sama"),
  typed("fe.notify", "fe", ["notify", "show"], "uživatel má vidět potvrzení nebo chybu", "stačí zápis do logu"),
  typed("be.endpoint", "be", ["input", "call-service"], "FE volá server", "volání zůstává uvnitř serveru"),
  typed("be.validate", "be", ["validate", "decide"], "vstup se musí ověřit před zpracováním", "ověření dělá DB omezením"),
  typed("be.function", "be", ["compute"], "je třeba spočítat hodnotu", "stačí přesun dat"),
  typed("db.write", "db", ["store"], "výsledek se má uložit trvale", "stačí dočasná hodnota"),
  typed("infra.api", "infra", ["call-service"], "voláš vnější službu", "služba je uvnitř aplikace"),
  { ...typed("ai.agent", "ai", ["ai"], "rozhoduje model", "stačí pravidlo"), category: "ai" },
  { ...typed("flow.if", "neutral", ["decide"], "tok se větví podle podmínky", "podmínka je v ověření"), category: "flow" },
  { type: "custom.step", version: 1, trigger: false, ports: step },
] as NodeTypeSpec[]).map((spec) => ({ ...spec, ...DATA_KINDS_OF[spec.type] }));
export const PROCESS = nodeTypeMap(PROCESS_TYPES);

export function processGraph(): FlowGraph {
  const node = (id: string, type: string, x: number, y: number) => ({ id, type, type_version: 1, params: {}, position: { x, y } });
  const edge = (id: string, source: string, target: string, via?: "http" | "sql" | "event" | "call" | "render") =>
    ({ id, source_node: source, source_port: "main", target_node: target, target_port: "main", kind: "main" as const, label: "", ...(via ? { via } : {}) });
  return {
    nodes: [node("formular", "fe.form", 0, 40), node("tlacitko", "fe.click", 260, 220), node("endpoint", "be.endpoint", 520, 60), node("kontrola", "be.validate", 780, 300),
      node("bmi", "be.function", 1040, 120), node("zapis", "db.write", 1300, 20), node("oznameni", "fe.notify", 1560, 260)],
    edges: [edge("e1", "formular", "tlacitko"), edge("e2", "tlacitko", "endpoint", "http"), edge("e3", "endpoint", "kontrola"), edge("e4", "kontrola", "bmi"),
      edge("e5", "bmi", "zapis", "sql"), edge("e6", "zapis", "oznameni", "event")],
    cases: [{ id: "v-poradku", name: "V pořádku", description: "Výška 180, váha 80 → BMI 24,7 → řádek v DB → notifikace", start: "formular",
      input: { vyska: 180, vaha: 80 }, env: { tables: { bmi: [] } },
      expect: { result: { bmi: 24.7 }, path: ["formular", "tlacitko", "endpoint", "kontrola", "bmi", "zapis", "oznameni"], rows: { bmi: [{ vyska: 180, vaha: 80, bmi: 24.7 }] }, notify: "BMI 24,7" } }],
  };
}
