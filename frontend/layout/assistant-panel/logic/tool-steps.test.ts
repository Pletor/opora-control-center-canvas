import { describe, expect, it } from "vitest";
import type { ChatItem } from "./assistant-events";
import { groupEntries, stepsLabel, stepsState, type ToolItem } from "./tool-steps";

const tool = (id: string, name: string, status: ToolItem["status"] = "ok"): ToolItem => ({ kind: "tool", id, name, summary: "", status, result: "" });
const msg = (id: string): ChatItem => ({ kind: "message", id, role: "assistant", text: id, streaming: false, origin: "live" });

describe("skupiny kroků", () => {
  it("po sobě jdoucí nástroje sbalí do jedné skupiny, zprávy je oddělí", () => {
    const entries = groupEntries([msg("a"), tool("1", "Read"), tool("2", "Grep"), msg("b"), tool("3", "Skill"), { kind: "error", id: "e", text: "x" }]);
    expect(entries.map((e) => e.kind)).toEqual(["message", "steps", "message", "steps", "error"]);
    expect(entries[1]).toMatchObject({ kind: "steps", id: "steps-1", tools: [{ id: "1" }, { id: "2" }] });
  });

  it("popisek skupiny s českým tvarem a jmény bez opakování", () => {
    expect(stepsLabel([tool("1", "Read")])).toBe("1 krok (Read)");
    expect(stepsLabel([tool("1", "Read"), tool("2", "Grep"), tool("3", "Read")])).toBe("3 kroky (Read, Grep)");
    const many = ["A", "B", "C", "D", "E"].map((n, i) => tool(String(i), n));
    expect(stepsLabel(many)).toBe("5 kroků (A, B, C, D, …)");
  });

  it("stav skupiny: běh a počet chyb", () => {
    expect(stepsState([tool("1", "Read", "running"), tool("2", "Grep", "error")])).toEqual({ running: true, errors: 1 });
    expect(stepsState([tool("1", "Read")])).toEqual({ running: false, errors: 0 });
  });
});
