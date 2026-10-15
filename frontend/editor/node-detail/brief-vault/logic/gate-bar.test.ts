import { describe, expect, it } from "vitest";
import type { GateFlags } from "./brief-vault-model";
import { GATES, formatError, gateBarLabel, gateDots, gateTitle, roundLabel, synthesizedView } from "./gate-bar";

const flags = (count: number): GateFlags => ({
  ...Object.fromEntries(GATES.map((gate, index) => [gate, index < count])) as Record<(typeof GATES)[number], boolean>,
  predictionError: null,
});

describe("gate bar", () => {
  it("has eight gates in the contract order with Czech titles", () => {
    expect(GATES).toEqual(["scoped", "weighed", "synthesized", "decided", "planned", "placed", "verified", "learned"]);
    expect(gateTitle("decided")).toBe("4. Rozhodnuto");
  });

  it("marks on, next and off dots", () => {
    const dots = gateDots({ gates: flags(2), gateStep: 2 });
    expect(dots.map((dot) => dot.state)).toEqual(["on", "on", "next", "off", "off", "off", "off", "off"]);
    expect(dots[2].label).toBe("3. Mikrokrok: další na řadě");
  });

  it("a dead end has no next gate and stale gates look different", () => {
    expect(gateDots({ gates: flags(4), gateStep: 4, deadEnd: true }).some((dot) => dot.state === "next")).toBe(false);
    expect(gateDots({ gates: flags(1), gateStep: 1, gatesStale: true }).map((dot) => dot.state))
      .toEqual(["on", "next", "stale", "stale", "stale", "stale", "stale", "stale"]);
    expect(gateDots({}).map((dot) => dot.state)[0]).toBe("next");
  });

  it("labels the bar and formats the prediction error", () => {
    expect(gateBarLabel({ gateStep: 3 })).toBe("3/8 bran · další: 4. Rozhodnuto");
    expect(gateBarLabel({ gateStep: 8 })).toBe("8/8 bran · cyklus uzavřen");
    expect(gateBarLabel({ gateStep: 4, deadEnd: true })).toContain("slepá ulička");
    expect(formatError(0.333)).toBe("0,33");
    expect(formatError(null)).toBe("—");
  });

  it("labels the round and the exhausted state", () => {
    expect(roundLabel({ round: 2, exhausted: false })).toEqual({ text: "kolo 2/3", exhausted: false });
    expect(roundLabel({ round: 4, exhausted: true })).toEqual({ text: "vyčerpáno – čeká na člověka", exhausted: true });
    expect(roundLabel({})).toBeNull();
    expect(gateBarLabel({ gateStep: 3, round: 2 })).toBe("3/8 bran · kolo 2/3 · další: 4. Rozhodnuto");
  });

  it("reads steps and layer of a synthesized payload", () => {
    expect(synthesizedView({ steps: ["A", "B"], layer: "database" })).toEqual({ steps: ["A", "B"], layer: "databáze" });
    expect(synthesizedView({ type: "x" })).toEqual({ steps: [], layer: null });
    expect(synthesizedView(null)).toEqual({ steps: [], layer: null });
  });
});
