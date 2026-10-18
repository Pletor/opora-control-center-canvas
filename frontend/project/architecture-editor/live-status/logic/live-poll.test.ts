import { describe, expect, it } from "vitest";
import { emptySlot, isStale, loadNotice, liveDelay, slotFailed, slotLoaded, slotLoading, staleNote, WORK_INTERVAL_MS } from "./live-poll";

describe("rytmus živého čtení", () => {
  it("bez chyby jede základní interval, po chybách odstup 10 → 20 → 60 s", () => {
    expect(liveDelay(WORK_INTERVAL_MS.detail, 0)).toBe(10_000);
    expect([1, 2, 3, 7].map((failures) => liveDelay(10_000, failures))).toEqual([10_000, 20_000, 60_000, 60_000]);
  });
  it("odstup nikdy nezrychlí pomalejší přehled", () => {
    expect(liveDelay(WORK_INTERVAL_MS.landing, 1)).toBe(30_000);
    expect(liveDelay(WORK_INTERVAL_MS.landing, 3)).toBe(60_000);
  });
});

describe("paměť posledních dat", () => {
  it("chyba nechá poslední data a označí je jako zastaralá s časem", () => {
    const at = new Date(2026, 9, 14, 12, 3).getTime();
    const loaded = slotLoaded(slotLoading(emptySlot<number>()), 7, at);
    expect(loaded).toMatchObject({ data: 7, failures: 0, loading: false });
    expect(staleNote(loaded)).toBe("");
    const failed = slotFailed(slotFailed(loaded, "síť"), "síť");
    expect(failed).toMatchObject({ data: 7, failures: 2, error: "síť" });
    expect(isStale(failed)).toBe(true);
    expect(staleNote(failed)).toBe("údaj z 12:03, nepodařilo se obnovit");
    expect(slotLoaded(failed, 8, at).failures).toBe(0);
  });
  it("chyba bez dat není zastaralý údaj", () => {
    const failed = slotFailed(emptySlot<number>(), "síť");
    expect(isStale(failed)).toBe(false);
    expect(staleNote(failed)).toBe("");
    expect(loadNotice(failed, "Stav práce")).toBe("Stav práce se nepodařilo načíst: síť");
    expect(loadNotice(slotFailed(slotLoaded(emptySlot<number>(), 1, 0), "síť"), "Stav práce")).toBe("");
    expect(loadNotice(emptySlot<number>(), "Stav práce")).toBe("");
  });
});
