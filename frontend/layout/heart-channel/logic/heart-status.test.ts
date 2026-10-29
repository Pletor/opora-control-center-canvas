import { describe, expect, it } from "vitest";
import type { HeartStatus } from "./heart-api";
import { statusLine } from "./heart-status";

const base: HeartStatus = {
  enabled: true, running: false, pending: 0, batches: [], sleeping: false, sleepingUntil: null,
  nextAllowedAt: "2026-10-29T10:00:00Z", error: null,
};
const NOW = Date.parse("2026-10-29T10:00:00Z");

describe("stav srdce", () => {
  it("chyba má přednost", () => {
    expect(statusLine({ ...base, running: true, error: "Claude Code nenalezen." }, NOW)).toEqual({
      tone: "error", text: "Chyba: Claude Code nenalezen.",
    });
  });

  it("pracuje, spí a probouzí se", () => {
    expect(statusLine({ ...base, running: true }, NOW).tone).toBe("working");
    expect(statusLine(base, NOW).tone).toBe("sleeping");
    expect(statusLine({ ...base, pending: 2 }, NOW)).toEqual({ tone: "working", text: "Probouzí se · 2 vstupy" });
  });

  it("čeká do času limitu nebo stropu", () => {
    const limited = statusLine({ ...base, sleeping: true, sleepingUntil: "2026-10-29T10:15:00Z" }, NOW);
    expect(limited.text).toMatch(/^Čeká do \d\d:\d\d \(limit předplatného\)$/);
    const capped = statusLine({ ...base, pending: 1, nextAllowedAt: "2026-10-29T10:40:00Z" }, NOW);
    expect(capped.tone).toBe("waiting");
    expect(capped.text).toMatch(/^Čeká do \d\d:\d\d · 1 vstup$/);
  });

  it("srdce, které na serveru neběží, přizná i čekající zprávy", () => {
    expect(statusLine({ ...base, enabled: false, pending: 5 }, NOW)).toEqual({
      tone: "off", text: "Srdce na tomto serveru neběží · čeká 5 vstupů",
    });
  });
});
