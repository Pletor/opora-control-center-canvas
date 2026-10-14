import { describe, expect, it } from "vitest";
import type { InboxItem } from "./tower-model";
import { ARM_MS, confirmLabel, confirmStep, idleConfirm, proposalsBySector } from "./inbox-actions";

const item = (kind: InboxItem["kind"], nodeId: string, sectorId: string): InboxItem =>
  ({ kind, nodeId, nodeName: nodeId, sectorId, sectorName: sectorId, areaId: "", areaName: "", text: "" });

describe("proposalsBySector", () => {
  it("bere jen návrhy uzavření v sektoru, bez duplicit a v pořadí fronty", () => {
    const map = proposalsBySector([
      item("proposed", "a", "s1"), item("waiting", "b", "s1"), item("proposed", "c", "s1"),
      item("proposed", "a", "s1"), item("proposed", "d", "s2"), item("proposed", "e", ""), item("stuck", "f", "s2"),
    ]);
    expect([...map.entries()]).toEqual([["s1", ["a", "c"]], ["s2", ["d"]]]);
  });
});

describe("confirmStep – dvojí klik", () => {
  it("první klik natáhne, druhý v limitu spustí, úspěch vrátí klid", () => {
    const armed = confirmStep(idleConfirm(), 1000);
    expect(armed).toEqual({ state: { kind: "armed", until: 1000 + ARM_MS }, run: false });
    expect(confirmLabel(armed.state, "Potvrdit")).toBe("Opravdu potvrdit");
    const busy = confirmStep(armed.state, 1000 + ARM_MS);
    expect(busy).toEqual({ state: { kind: "busy" }, run: true });
    expect(confirmLabel(busy.state, "Potvrdit")).toBe("ukládám…");
    expect(confirmStep(busy.state, 2000)).toEqual({ state: { kind: "busy" }, run: false });
    expect(confirmStep(busy.state, 2000, { type: "success" }).state).toEqual(idleConfirm());
  });

  it("po vypršení limitu se tlačítko vrátí do klidu a klik natahuje znovu", () => {
    const armed = confirmStep(idleConfirm(), 0).state;
    expect(confirmStep(armed, ARM_MS - 1, { type: "tick" }).state).toBe(armed);
    expect(confirmStep(armed, ARM_MS + 1, { type: "tick" }).state).toEqual(idleConfirm());
    expect(confirmStep(armed, ARM_MS + 1)).toEqual({ state: { kind: "armed", until: 2 * ARM_MS + 1 }, run: false });
  });

  it("chyba zůstane jako text a další klik začíná znovu natažením", () => {
    const error = confirmStep({ kind: "busy" }, 0, { type: "failure", message: "konflikt revize" }).state;
    expect(error).toEqual({ kind: "error", message: "konflikt revize" });
    expect(confirmLabel(error, "Potvrdit")).toBe("Potvrdit");
    expect(confirmStep({ kind: "busy" }, 0, { type: "failure", message: "" }).state).toEqual({ kind: "error", message: "Potvrzení se neuložilo." });
    expect(confirmStep(error, 10)).toEqual({ state: { kind: "armed", until: 10 + ARM_MS }, run: false });
  });
});
