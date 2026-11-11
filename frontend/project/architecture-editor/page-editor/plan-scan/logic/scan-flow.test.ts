import { describe, expect, it } from "vitest";
import { flowSize, scanFlowGraph } from "./scan-flow";

const empty = { inputs: [], steps: [], outputs: [], conditions: [], dataTo: [] };

describe("tok prvku ze skenu jako graf plátna logiky", () => {
  it("vstupy → podmínky (true) → kroky → výstupy a cíle dat", () => {
    const flow = { inputs: ["E-mail", "Heslo"], conditions: ["Účet existuje"], steps: ["Ověřit heslo", "Založit relaci"], outputs: ["Přesměrování"], dataTo: ["Databáze účtů"] };
    const graph = scanFlowGraph(flow);
    expect(graph.nodes.map((node) => node.id)).toEqual(["vstup-1", "vstup-2", "podminka-1", "krok-1", "krok-2", "vystup-1", "data-1"]);
    expect(flowSize(flow)).toBe(7);
    expect(graph.edges.map((edge) => `${edge.source_node}.${edge.source_port}>${edge.target_node}`)).toEqual([
      "vstup-1.main>podminka-1", "vstup-2.main>podminka-1", "podminka-1.true>krok-1", "krok-1.main>krok-2", "krok-2.main>vystup-1", "krok-2.main>data-1"]);
    const step = graph.nodes.find((node) => node.id === "krok-1")!;
    expect(step).toMatchObject({ type: "custom.step", layer: "neutral", params: { title: "Ověřit heslo" }, notes: "Ověřit heslo", notesInFlow: true });
    expect(graph.nodes.find((node) => node.id === "podminka-1")).toMatchObject({ type: "flow.if", notes: "Účet existuje" });
    expect(graph.edges.every((edge) => edge.kind === "main" && edge.target_port === "main")).toBe(true);
    // Výstup a cíl dat stojí v jednom sloupci pod sebou, napravo od posledního kroku.
    const at = (id: string) => graph.nodes.find((node) => node.id === id)!.position!;
    expect(at("vystup-1").x).toBe(at("data-1").x);
    expect(at("vystup-1").x).toBeGreaterThan(at("krok-2").x);
    expect(at("data-1").y).toBeGreaterThan(at("vystup-1").y);
  });
  it("bez vstupů začíná tok prvním krokem; prázdný tok je prázdný graf", () => {
    const graph = scanFlowGraph({ ...empty, steps: ["Odeslat"], outputs: ["Potvrzení"] });
    expect(graph.edges.map((edge) => edge.id)).toEqual(["krok-1-vystup-1"]);
    expect(scanFlowGraph(empty)).toEqual({ nodes: [], edges: [] });
  });
  it("$( v textu neudělá odkaz na uzel", () => {
    expect(scanFlowGraph({ ...empty, steps: ["Spočítat $('cena')"] }).nodes[0].params).toMatchObject({ title: "Spočítat $ ('cena')" });
  });
});
