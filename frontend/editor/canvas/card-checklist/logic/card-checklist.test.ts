import { describe, expect, it } from "vitest";
import { areaSummary, handoffMark, nodeKinds, type CheckItem, type CheckKey, type CheckState } from "@/editor/canvas/card-checklist/logic/card-checklist";
import { emptyDesktopState, type DesktopState } from "@/shared/desktop-state/logic/types";

const item = (key: CheckKey, state: CheckState, hint = ""): CheckItem => ({ key, label: key, state, hint });
const nodes = nodeKinds([{ id: "a", kind: "node" as const }, { id: "b", kind: "node" as const }, { id: "c", kind: "comment" as const }]);
const edge = { id: "e", source: "a", target: "b", port: "next" as const };
const done = (confirmed: boolean, by: "human" | "agent"): DesktopState => ({
  ...emptyDesktopState(), nodes: { a: { phase: "build", criteria: [], steps: [], done: { confirmed, at: "", by, note: "" } } },
});

describe("kontrolní pás karty", () => {
  it("souhrn oblasti počítá jen hotová pole a karty čekající na člověka", () => {
    const summary = areaSummary([[item("pipeline", "yes"), item("evidence", "no")], [item("pipeline", "run"), item("blocks", "fail")]]);
    expect(summary.total).toBe(2);
    expect(summary.bars.find((b) => b.key === "pipeline")?.value).toBe(1);
    expect(summary.waiting).toBe(1);
  });

  it("obálka je jen u vazby mezi kartami: předáno, nebo chybí po dokončení zdroje", () => {
    expect(handoffMark(edge, emptyDesktopState(), nodes)).toBeNull();
    expect(handoffMark(edge, done(false, "agent"), nodes)).toBe("missing");
    expect(handoffMark(edge, done(false, "human"), nodes)).toBeNull();
    const sent = { ...done(true, "human"), edges: { e: { log: "", summary: "", handoff: "Pokračuj v B.", improvements: "", errors: "", updatedAt: "", by: "agent" as const, agent: "worker" } } };
    expect(handoffMark(edge, sent, nodes)).toBe("sent");
    expect(handoffMark({ ...edge, port: "rule" }, sent, nodes)).toBeNull();
    expect(handoffMark({ ...edge, source: "c" }, sent, nodes)).toBeNull();
  });
});
