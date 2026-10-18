import { describe, expect, it } from "vitest";
import type { InboxItem } from "./tower-model";
import {
  ARM_GUARD_MS, ARM_MS, armedText, confirmLabel, confirmStep, confirmSummary, idleConfirm, proposalsBySector, runConfirm, sameScope, scopeLocked,
} from "./inbox-actions";

const item = (kind: InboxItem["kind"], nodeId: string, sectorId: string): InboxItem =>
  ({ kind, nodeId, nodeName: nodeId, sectorId, sectorName: sectorId, areaId: "", areaName: "", text: "" });
const click = (scope: string[]) => ({ type: "click" as const, scope });
const name = (id: string) => id.toUpperCase();

describe("proposalsBySector a rozsah", () => {
  it("bere jen návrhy uzavření v sektoru, bez duplicit a v pořadí fronty", () => {
    const map = proposalsBySector([
      item("proposed", "a", "s1"), item("waiting", "b", "s1"), item("proposed", "c", "s1"),
      item("proposed", "a", "s1"), item("proposed", "d", "s2"), item("proposed", "e", ""), item("stuck", "f", "s2"),
    ]);
    expect([...map.entries()]).toEqual([["s1", ["a", "c"]], ["s2", ["d"]]]);
  });

  it("porovná rozsah bez ohledu na pořadí a pozná zámek", () => {
    expect(sameScope(["a", "b"], ["b", "a"])).toBe(true);
    expect(sameScope(["a"], ["a", "b"])).toBe(false);
    expect(scopeLocked(["a", "b"], new Set(["b"]))).toBe(true);
    expect(scopeLocked(["a"], new Set(["b"]))).toBe(false);
  });
});

describe("confirmStep – dvojí klik s rozsahem", () => {
  it("první klik natáhne s rozsahem, druhý po pojistce potvrdí právě ten rozsah", () => {
    const armed = confirmStep(idleConfirm(), 1000, click(["a", "b"]));
    expect(armed).toEqual({ state: { kind: "armed", since: 1000, until: 1000 + ARM_MS, scope: ["a", "b"] }, run: null });
    expect(confirmLabel(armed.state, "Potvrdit", "Opravdu?")).toBe("Opravdu?");
    expect(confirmStep(armed.state, 1000 + ARM_GUARD_MS - 1, click(["a", "b"]))).toEqual({ state: armed.state, run: null });
    const busy = confirmStep(armed.state, 1000 + ARM_GUARD_MS, click(["b", "a"]));
    expect(busy).toEqual({ state: { kind: "busy", scope: ["a", "b"] }, run: ["a", "b"] });
    expect(confirmLabel(busy.state, "Potvrdit", "Opravdu?")).toBe("ukládám…");
    expect(confirmStep(busy.state, 3000, click(["a", "b"])).run).toBeNull();
    expect(confirmStep(busy.state, 3000, { type: "result", message: "", failed: false }).state).toEqual(idleConfirm());
  });

  it("změna seznamu natažení zruší; po vypršení se vrací do klidu", () => {
    const armed = confirmStep(idleConfirm(), 0, click(["a", "b"])).state;
    const stale = confirmStep(armed, 10, { type: "scope", scope: ["a"] }).state;
    expect(stale).toEqual({ kind: "stale" });
    expect(confirmLabel(stale, "Potvrdit", "x")).toBe("Seznam se změnil, klikni znovu");
    expect(confirmStep(armed, 10, { type: "scope", scope: ["b", "a"] }).state).toBe(armed);
    expect(confirmStep(armed, 1000, click(["a"])).state).toEqual({ kind: "stale" });
    expect(confirmStep(stale, 2000, click(["a"])).state).toMatchObject({ kind: "armed", scope: ["a"] });
    expect(confirmStep(armed, ARM_MS - 1, { type: "tick" }).state).toBe(armed);
    expect(confirmStep(armed, ARM_MS + 1, { type: "tick" }).state).toEqual(idleConfirm());
    expect(confirmStep(armed, ARM_MS + 1, click(["a", "b"])).state).toMatchObject({ kind: "armed", since: ARM_MS + 1 });
    expect(confirmStep(idleConfirm(), 0, click([])).state).toEqual(idleConfirm());
  });

  it("výsledek s hláškou zůstane jako done nebo error", () => {
    expect(confirmStep({ kind: "busy", scope: ["a"] }, 0, { type: "result", message: "Uzavřeno 2.", failed: false }).state).toEqual({ kind: "done", message: "Uzavřeno 2." });
    expect(confirmStep({ kind: "busy", scope: ["a"] }, 0, { type: "result", message: "selhalo", failed: true }).state).toEqual({ kind: "error", message: "selhalo" });
    expect(confirmStep({ kind: "busy", scope: ["a"] }, 0, { type: "failure", message: "" }).state).toEqual({ kind: "error", message: "Potvrzení se neuložilo." });
  });
});

describe("texty a potvrzování", () => {
  it("natažený text nese rozsah a souhrn počítá uzavřené i selhané", () => {
    expect(armedText(["a"], name, false)).toBe("Opravdu uzavřít „A“?");
    expect(armedText(["a", "b"], name, true)).toBe("Opravdu uzavřít 2 karty v sektoru?");
    expect(confirmSummary({ ok: ["a"], failed: [] }, name)).toBe("");
    expect(confirmSummary({ ok: ["a", "b"], failed: [] }, name)).toBe("Uzavřeno 2.");
    expect(confirmSummary({ ok: ["a", "b"], failed: [{ id: "c", error: "konflikt" }] }, name)).toBe("Uzavřeno 2, selhalo 1: C — konflikt");
  });

  it("po kartách sekvenčně, chyba jedné nezastaví ostatní", async () => {
    const order: string[] = [];
    const one = async (id: string) => {
      order.push(id);
      if (id === "b") throw new Error("konflikt");
      return id !== "c";
    };
    const result = await runConfirm(["a", "b", "c", "d"], "s", one, async () => { throw new Error("nesmí"); });
    expect(order).toEqual(["a", "b", "c", "d"]);
    expect(result).toEqual({ ok: ["a", "d"], failed: [{ id: "b", error: "Error: konflikt" }, { id: "c", error: "neuloženo" }] });
  });

  it("bez potvrzení po kartách použije hromadné za sektor", async () => {
    const calls: [string, string[]][] = [];
    expect(await runConfirm(["a", "b"], "s", undefined, async (s, ids) => void calls.push([s, ids]))).toEqual({ ok: ["a", "b"], failed: [] });
    expect(calls).toEqual([["s", ["a", "b"]]]);
    expect(await runConfirm(["a"], "s", undefined, async () => { throw new Error("x"); })).toEqual({ ok: [], failed: [{ id: "a", error: "Error: x" }] });
    expect((await runConfirm(["a"], "", undefined, undefined)).failed).toHaveLength(1);
  });
});
