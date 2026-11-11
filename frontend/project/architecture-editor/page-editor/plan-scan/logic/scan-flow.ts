// Tok prvku ze skenu webu → první verze plátna logiky prvku (docs/navrhy/2026-11-10-platno-2.md, Verze 6): vstupy →
// podmínky (větvení) → kroky → výstupy a cíle dat. Jen existující typy katalogu toků dat (`backend/flow/catalogs/`):
// text bez typu = krok na míru `custom.step` (vrstva neutral, titulek), podmínka = `flow.if` (pokračuje `true`,
// `false` zůstane volné). Id uzlu je čitelné, protože ho karta ukazuje jako jméno; text jde i do poznámky na kartě.
// Bez Reactu, test vedle.
import type { FlowEdge, FlowGraph, FlowNode } from "@/shared/flow-editor/logic/flow-types";
import type { ScanFlow } from "./page-scan";

const COLUMN = 280, ROW = 140;
// `$(` v textu by `graph_check` četl jako odkaz na uzel `$('id')`.
const safe = (value: string) => value.replace(/\$\(/g, "$ (");

/** Počet uzlů, které tok založí (náhled v panelu skenu). */
export const flowSize = (flow: ScanFlow) => flow.inputs.length + flow.conditions.length + flow.steps.length + flow.outputs.length + flow.dataTo.length;

type Part = { items: string[]; prefix: string; description: string; condition?: boolean };

export function scanFlowGraph(flow: ScanFlow): FlowGraph {
  const nodes: FlowNode[] = [], edges: FlowEdge[] = [];
  let column = 0;
  /** Konce, ze kterých tok pokračuje: [uzel, výstupní port]. */
  let tails: [string, string][] = [];
  const node = ({ prefix, description, condition }: Part, text: string, index: number, x: number, y: number): FlowNode => condition
    ? { id: `${prefix}-${index + 1}`, type: "flow.if", type_version: 1, params: {}, notes: safe(text), notesInFlow: true, position: { x, y } }
    : { id: `${prefix}-${index + 1}`, type: "custom.step", type_version: 1, layer: "neutral", params: { title: safe(text), description },
      notes: safe(text), notesInFlow: true, position: { x, y } };
  const link = (target: string) => tails.forEach(([source, port]) =>
    edges.push({ id: `${source}-${target}`, source_node: source, source_port: port, target_node: target, target_port: "main", kind: "main", label: "" }));
  /** Sloupec pod sebou (vstupy, výstupy, cíle dat): hrana z každého konce do každého uzlu; `row` = první řádek sloupce. */
  const fan = (part: Part, row = 0) => {
    if (!part.items.length) return;
    const made = part.items.map((text, index) => node(part, text, index, column * COLUMN, (row + index) * ROW));
    made.forEach((item) => link(item.id));
    nodes.push(...made);
    return made.map((item): [string, string] => [item.id, "main"]);
  };
  /** Řetěz zleva doprava (podmínky, kroky): každý uzel navazuje na předchozí, podmínka pokračuje výstupem `true`. */
  const chain = (part: Part) => part.items.forEach((text, index) => {
    const made = node(part, text, index, column * COLUMN, 0);
    link(made.id); nodes.push(made); tails = [[made.id, part.condition ? "true" : "main"]]; column += 1;
  });
  const inputs = fan({ items: flow.inputs, prefix: "vstup", description: "Vstup" });
  if (inputs) { tails = inputs; column += 1; }
  chain({ items: flow.conditions, prefix: "podminka", description: "Podmínka", condition: true });
  chain({ items: flow.steps, prefix: "krok", description: "Krok" });
  // Výstupy a pod nimi cíle dat jsou v jednom sloupci; data do obou tečou ze stejného konce toku.
  fan({ items: flow.outputs, prefix: "vystup", description: "Výstup" });
  fan({ items: flow.dataTo, prefix: "data", description: "Kam data odcházejí" }, flow.outputs.length);
  return { nodes, edges };
}
