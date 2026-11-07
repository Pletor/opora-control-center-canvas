import { describe, expect, it } from "vitest";
import { escTarget, keepScroll } from "./linie-keep";

describe("stálá poloha výběru", () => {
  it("tatáž kulička se posunula o Δy → scrollTop += Δy", () => {
    expect(keepScroll({ id: "a", y: 300 }, { id: "a", y: 420 }, 100)).toBe(220);
    expect(keepScroll({ id: "a", y: 300 }, { id: "a", y: 200 }, 50)).toBe(0); // nikdy pod nulu
  });
  it("nový výběr, zmizelá kulička nebo žádný výběr nic nemění", () => {
    expect(keepScroll({ id: "a", y: 300 }, { id: "b", y: 500 }, 100)).toBe(100);
    expect(keepScroll({ id: "a", y: 300 }, null, 100)).toBe(100);
    expect(keepScroll(null, { id: "a", y: 300 }, 100)).toBe(100);
  });
});

describe("pořadí Esc", () => {
  it("přejmenování → Cesta → commit → detail → nic", () => {
    const all = { renaming: true, trace: true, commit: true, detail: true };
    expect(escTarget(all)).toBe("renaming");
    expect(escTarget({ ...all, renaming: false })).toBe("trace");
    expect(escTarget({ ...all, renaming: false, trace: false })).toBe("commit");
    expect(escTarget({ renaming: false, trace: false, commit: false, detail: true })).toBe("detail");
    expect(escTarget({ renaming: false, trace: false, commit: false, detail: false })).toBeNull();
  });
});
