import { describe, expect, it } from "vitest";
import type { CanvasNode } from "@/shared/types/logic/types";
import { boxBadges } from "./box-badges";

const node = (id: string): CanvasNode => ({ id, parentId: "p", kind: "node", name: id, purpose: "", x: 0, y: 0, element: { kind: "action" } });
const states = new Map([["a", { state: "done" as const }], ["b", { state: "building" as const }], ["v", { state: "verified" as const }]]);

describe("značky boxu", () => {
  it("prázdný box nemá milník ani Ověřeno", () => {
    expect(boxBadges({}, [], states, false)).toEqual({ sketch: false, inspirations: 0, logic: 0, worst: null, verified: false, proposed: false });
  });
  it("nejhorší milník určí nejpomalejší prvek; neznámý stav = Návrh", () => {
    expect(boxBadges({}, [node("a"), node("b")], states, false).worst).toBe("Realizace");
    expect(boxBadges({}, [node("a"), node("x")], states, false).worst).toBe("Návrh");
    expect(boxBadges({}, [node("a")], states, false).worst).toBe("Ověření");
  });
  it("všechny prvky ověřené = Ověřeno bez milníku", () => {
    expect(boxBadges({}, [node("v")], states, false)).toMatchObject({ logic: 1, worst: null, verified: true });
  });
  it("skica, inspirace (obrázky + odkaz) a návrh", () => {
    expect(boxBadges({ status: "proposed", inspiration: { files: ["f1", "f2"], url: "https://x.cz" } }, [], states, true))
      .toMatchObject({ sketch: true, inspirations: 3, proposed: true });
  });
});
