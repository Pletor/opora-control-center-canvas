import { describe, expect, it } from "vitest";
import { AUTOSAVE_MS, autosaveDelay, saveOnLeave, warnOnUnload, type SaveGate } from "./storyboard-autosave";

const gate = (patch: Partial<SaveGate> = {}): SaveGate => ({ dirty: true, valid: true, readOnly: false, status: "idle", ...patch });

describe("automatické ukládání storyboardu", () => {
  it("neuložený platný koncept se uloží 700 ms po poslední změně", () => {
    expect(autosaveDelay(gate(), false, false)).toBe(AUTOSAVE_MS);
    expect(AUTOSAVE_MS).toBe(700);
  });
  it("změna během ukládání se uloží hned po jeho dokončení", () => {
    expect(autosaveDelay(gate(), true, false)).toBe(0);
  });
  it("neukládá uložený, chybný ani jen ke čtení", () => {
    expect(autosaveDelay(gate({ dirty: false }), false, false)).toBeNull();
    expect(autosaveDelay(gate({ valid: false }), false, false)).toBeNull();
    expect(autosaveDelay(gate({ readOnly: true }), false, false)).toBeNull();
  });
  it("čeká při ukládání, načítání a konfliktu", () => {
    for (const status of ["saving", "loading", "conflict"] as const) expect(autosaveDelay(gate({ status }), true, false)).toBeNull();
  });
  it("po chybě zkusí znovu až po další změně", () => {
    expect(autosaveDelay(gate({ status: "error" }), false, true)).toBeNull();
    expect(autosaveDelay(gate({ status: "error" }), false, false)).toBe(AUTOSAVE_MS);
  });
});

describe("odchod z karty", () => {
  it("uloží neuložený platný koncept v klidu nebo po chybě", () => {
    expect(saveOnLeave(gate())).toBe(true);
    expect(saveOnLeave(gate({ status: "error" }))).toBe(true);
  });
  it("neukládá uložený, chybný, jen ke čtení, při ukládání, konfliktu a načítání", () => {
    expect(saveOnLeave(gate({ dirty: false }))).toBe(false);
    expect(saveOnLeave(gate({ valid: false }))).toBe(false);
    expect(saveOnLeave(gate({ readOnly: true }))).toBe(false);
    for (const status of ["saving", "loading", "conflict"] as const) expect(saveOnLeave(gate({ status }))).toBe(false);
  });
  it("varuje jen když se koncept uložit nedá", () => {
    expect(warnOnUnload(gate())).toBe(false);
    expect(warnOnUnload(gate({ status: "saving" }))).toBe(false);
    expect(warnOnUnload(gate({ status: "error" }))).toBe(true);
    expect(warnOnUnload(gate({ status: "conflict" }))).toBe(true);
    expect(warnOnUnload(gate({ valid: false }))).toBe(true);
    expect(warnOnUnload(gate({ dirty: false, status: "error" }))).toBe(false);
    expect(warnOnUnload(gate({ readOnly: true, status: "error" }))).toBe(false);
  });
});
