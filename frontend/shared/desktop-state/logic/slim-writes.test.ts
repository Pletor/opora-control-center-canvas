import { describe, expect, it } from "vitest";
import { appliesTo, stateChange, withItem, withItems, withNode, withStages } from "@/shared/desktop-state/logic/slim-writes";
import { emptyDesktopState, type Decision, type Rule } from "@/shared/desktop-state/logic/types";
import type { CardPipeline } from "@/editor/workflow/card-pipeline/logic/pipeline-model";

const decision = (id: string, text = id): Decision =>
  ({ id, text, pinned: false, path: "", nodeId: "", createdAt: "2026-10-10T00:00:00+00:00", by: "human" }) as Decision;
const rule = (id: string): Rule => ({ id, text: id, kind: "must", scope: "project", target: "" }) as Rule;

describe("slim write responses", () => {
  it("applies only the response of exactly this one write", () => {
    expect(appliesTo(4, { revision: 5 })).toBe(true);
    expect(appliesTo(4, { revision: 6 })).toBe(false); // mezitím zapsal někdo jiný
    expect(appliesTo(4, { revision: 5, graphChanged: true })).toBe(false); // zápis změnil i graf
  });

  it("adds at the end, updates in place and removes like MemoryItems on the server", () => {
    const base = { ...emptyDesktopState(), decisions: [decision("a"), decision("b")], rules: [rule("r")] };
    expect(withItem(base, "decision", "c", decision("c")).decisions.map((d) => d.id)).toEqual(["a", "b", "c"]);
    const updated = withItem(base, "decision", "a", decision("a", "nový"));
    expect(updated.decisions.map((d) => [d.id, d.text])).toEqual([["a", "nový"], ["b", "b"]]);
    expect(withItem(base, "decision", "b", null).decisions.map((d) => d.id)).toEqual(["a"]);
    expect(withItem(base, "rule", "r", { ...rule("r"), by: "agent" } as Rule).rules[0]).toMatchObject({ id: "r", by: "agent" });
    expect(base.decisions.map((d) => d.id)).toEqual(["a", "b"]); // původní stav zůstal beze změny
    expect(updated.rules).toBe(base.rules);
  });

  it("sets new stages on the node and creates a missing node like the server", () => {
    const stages = { profile: "code", items: [], routedBy: "human", reason: "x" } as unknown as CardPipeline;
    const base = { ...emptyDesktopState(), nodes: { n1: { phase: "build" as const, criteria: [], steps: [], blocks: [] } } };
    expect(withStages(base, "n1", stages).nodes.n1).toEqual({ phase: "build", criteria: [], steps: [], blocks: [], stages });
    expect(withStages(base, "n2", stages).nodes.n2).toEqual({ phase: "discover", criteria: [], steps: [], stages });
    expect(base.nodes.n1).not.toHaveProperty("stages");
  });

  it("sends one changed card as a slim node write and anything else as the full state", () => {
    const card = (phase: "discover" | "build") => ({ phase, criteria: [], steps: [], blocks: [] });
    const base = { ...emptyDesktopState(), nodes: { a: card("discover"), b: card("discover") } };
    const edited = { ...base, nodes: { ...base.nodes, a: card("build") } };
    expect(stateChange(base, edited)).toEqual({ kind: "node", nodeId: "a", node: card("build") });
    expect(stateChange(base, { ...base, nodes: { ...base.nodes, c: card("build") } })).toEqual({ kind: "node", nodeId: "c", node: card("build") });
    const { b: _removed, ...rest } = base.nodes;
    expect(stateChange(base, { ...base, nodes: rest })).toEqual({ kind: "node", nodeId: "b", node: null });
    // Stejný obsah pod novou referencí (mutace přestaví všechny uzly) se za změnu nepočítá.
    const rebuilt = { ...base, nodes: { a: card("build"), b: card("discover") } };
    expect(stateChange(base, rebuilt)).toEqual({ kind: "node", nodeId: "a", node: card("build") });
    expect(stateChange(base, { ...base, nodes: { a: card("build"), b: card("build") } })).toEqual({ kind: "full" });
    expect(stateChange(base, { ...edited, rules: [rule("r")] })).toEqual({ kind: "full" });
    expect(stateChange(base, { ...edited, edges: { e1: {} as never } })).toEqual({ kind: "full" });
    expect(stateChange(base, base)).toEqual({ kind: "none" });
    expect(stateChange(base, { ...base, nodes: { a: card("discover"), b: card("discover") } })).toEqual({ kind: "none" });
  });

  it("puts the saved node into the state like the server and keeps other cards' references", () => {
    const a = { phase: "build" as const, criteria: [], steps: [] };
    const b = { phase: "define" as const, criteria: [], steps: [] };
    const base = { ...emptyDesktopState(), nodes: { a, b } };
    const replaced = withNode(base, "a", { ...a, phase: "verify" });
    expect(replaced.nodes.a.phase).toBe("verify");
    expect(replaced.nodes.b).toBe(b);
    expect(replaced.rules).toBe(base.rules);
    expect(Object.keys(withNode(base, "b", null).nodes)).toEqual(["a"]);
    expect(base.nodes.a).toBe(a); // původní stav zůstal beze změny
  });
});

it("applies a whole batch review of one revision: approved stay in place, rejected disappear", () => {
  const proposal = (id: string): Rule => ({ ...rule(id), by: "agent" });
  const base = { ...emptyDesktopState(), rules: [proposal("a"), proposal("b"), proposal("c")] };
  const next = withItems(base, "rule", [{ id: "a", item: rule("a") }, { id: "c", item: null }]);
  expect(next.rules).toEqual([rule("a"), proposal("b")]);
});
