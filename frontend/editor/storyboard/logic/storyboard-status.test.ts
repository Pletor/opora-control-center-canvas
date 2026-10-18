import { describe, expect, it } from "vitest";
import { clockTime, commentsWaiting, statusLabel } from "./storyboard-status";

const base = { status: "idle" as const, dirty: false, autosave: true, message: "", savedAt: null, openComments: 0 };

describe("štítek stavu storyboardu", () => {
  it("skloňuje počet komentářů česky", () => {
    expect(commentsWaiting(1)).toBe("1 komentář čeká na agenta");
    expect(commentsWaiting(2)).toBe("2 komentáře čekají na agenta");
    expect(commentsWaiting(4)).toBe("4 komentáře čekají na agenta");
    expect(commentsWaiting(5)).toBe("5 komentářů čeká na agenta");
    expect(commentsWaiting(12)).toBe("12 komentářů čeká na agenta");
  });
  it("čas uložení jako HH:MM", () => {
    expect(clockTime(new Date(2026, 9, 16, 9, 5))).toBe("09:05");
  });
  it("uloženo s časem a čekajícími komentáři", () => {
    expect(statusLabel({ ...base, savedAt: new Date(2026, 9, 16, 14, 7), openComments: 2 })).toEqual({ text: "Uloženo 14:07 · 2 komentáře čekají na agenta", tone: "quiet" });
    expect(statusLabel(base).text).toBe("Uloženo");
  });
  it("neuložený koncept se brzy uloží, chybný ukáže důvod", () => {
    expect(statusLabel({ ...base, dirty: true })).toEqual({ text: "Neuloženo · ukládám za chvíli", tone: "dirty" });
    expect(statusLabel({ ...base, dirty: true, autosave: false, message: "Moment bez času" })).toEqual({ text: "Neuloženo: Moment bez času", tone: "warn" });
  });
  it("ukládání, konflikt a chyba", () => {
    expect(statusLabel({ ...base, status: "saving", dirty: true }).text).toBe("Ukládám…");
    expect(statusLabel({ ...base, status: "conflict", message: "stará revize" })).toEqual({ text: "Změněno jinde: stará revize", tone: "warn" });
    expect(statusLabel({ ...base, status: "error", message: "HTTP 500" })).toEqual({ text: "Chyba: HTTP 500", tone: "warn" });
  });
});
