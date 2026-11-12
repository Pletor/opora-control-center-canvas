import { describe, expect, it } from "vitest";
import { autonomyVerdict, waitingForHuman } from "./autonomy-waiting";

describe("waitingForHuman – co čeká na člověka", () => {
  it("bere jen blokace kvůli člověku a bráně, s názvem rozhodnutí", () => {
    const state = {
      actions: [
        { id: "a1", verb: "accept", targetId: "92335618ee81", status: "blocked", blockReason: "gate_required" },
        { id: "a2", verb: "close_card", targetId: "n0", status: "blocked", blockReason: "human_only" },
        { id: "a3", verb: "claim", targetId: "n1", status: "blocked", blockReason: "budget" },
        { id: "a4", verb: "accept", targetId: "x", status: "ready" },
      ],
      decisions: [{ actionId: "a1", title: "Plán srdce: 2 uzlů" }],
    };
    expect(waitingForHuman(state)).toEqual([
      { id: "a1", what: "Plán srdce: 2 uzlů", target: "92335618", reason: "brána mozku agenta nepustí – zapněte průchod bránou" },
      { id: "a2", what: "Uzavření karty", target: "n0", reason: "jen člověk – zapněte plnou autonomii" },
    ]);
  });
  it.each([[null], [{}], [{ actions: "x" }]])("cizí tvar %j = nic", (state) => {
    expect(waitingForHuman(state)).toEqual([]);
  });
});

describe("autonomyVerdict", () => {
  it("rozliší vypnuto, zavřenou bránu a samostatné agenty", () => {
    expect(autonomyVerdict(false, { on: false, passes: false })).toMatch(/čekají na člověka/);
    expect(autonomyVerdict(true, { on: true, passes: false })).toMatch(/brána mozku/);
    expect(autonomyVerdict(true, { on: true, passes: true })).toMatch(/sami/);
    expect(autonomyVerdict(true, { on: false, passes: false })).toMatch(/sami/);
  });
});
