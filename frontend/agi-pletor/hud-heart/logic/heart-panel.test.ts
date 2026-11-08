import { describe, expect, it } from "vitest";
import type { HeartStatus } from "@/layout/heart-channel/logic/heart-api";
import { IDLE_POLL_MS, STEPS_SHOWN, WORK_POLL_MS, elapsed, heartPanel, oneLine, pollMs, typical } from "./heart-panel";

const NOW = Date.parse("2026-11-08T10:02:14Z");
const idle: HeartStatus = {
  enabled: true, running: false, pending: 0, batches: [], sleeping: false, sleepingUntil: null, nextAllowedAt: null, error: null,
};
const running: HeartStatus = {
  ...idle, running: true, typicalMs: 180_000,
  current: {
    startedAt: "2026-11-08T10:00:00Z",
    inputs: [{ type: "message", text: "Prosím   projdi\nPR #42 a shrň změny v bráně" }],
    steps: Array.from({ length: 8 }, (_, i) => ({ t: i * 1000, kind: "tool" as const, text: `krok ${i}` })),
  },
};
const panel = (status: HeartStatus | null, answered = false) => heartPanel({ status, answered, now: NOW });

describe("heartPanel stavy", () => {
  it("pracuje: čas od začátku, obvyklá délka, co ho probudilo a posledních 6 kroků (nejnovější dole)", () => {
    const view = panel(running);
    expect(view.kind).toBe("working");
    expect(view.title).toBe("Srdce pracuje · 2:14 (obvykle ~3 min)");
    expect(view.detail).toBe("probudilo: zpráva člověka · „Prosím projdi PR #42 a shrň změny v bráně“");
    expect(view.hint).toBe("Můžeš mluvit s Pletorem, Srdce pracuje na pozadí.");
    expect(view.steps).toHaveLength(STEPS_SHOWN);
    expect(view.steps.at(-1)?.text).toBe("krok 7");
  });
  it("pracuje bez `current` (starý backend) jen větou", () => {
    expect(panel({ ...idle, running: true })).toMatchObject({ kind: "working", title: "Srdce pracuje", detail: "", steps: [] });
  });
  it("fronta, chyba a spánek se souhrnem poslední dávky", () => {
    expect(panel({ ...idle, pending: 3 }).title).toBe("Srdce má ve frontě 3 vstupy, za chvíli začne.");
    expect(panel({ ...idle, pending: 2, sleeping: true, sleepingUntil: null }).title).toBe("Srdce má ve frontě 2 vstupy, čeká na limit předplatného.");
    expect(panel({ ...idle, error: "limit" })).toMatchObject({ kind: "error", title: "Chyba srdce: limit" });
    const batches = [
      { at: "2026-11-08T09:30:00Z", status: "ok", costUsd: null, summary: "Sloučil PR #41" },
      { at: "2026-11-08T09:00:00Z", status: "ok", costUsd: null, summary: "starší" },
    ];
    expect(panel({ ...idle, batches })).toMatchObject({ kind: "sleeping", title: "Srdce spí", detail: "naposledy: Sloučil PR #41" });
    expect(panel(idle).detail).toBe("");
  });
  it("nedostupný stav, když dotaz selhal", () => {
    expect(panel(null)).toMatchObject({ kind: "unavailable", title: "Stav srdce nedostupný" });
  });
});

describe("heartPanel přednost", () => {
  it("odpověď připravená přebije práci, frontu, chybu, spánek i nedostupný stav", () => {
    for (const status of [running, { ...idle, pending: 2 }, { ...idle, error: "x" }, idle, null]) {
      expect(panel(status, true).kind).toBe("answer");
    }
    expect(panel(idle, true).title).toBe("Srdce má odpověď na tvou otázku · mluv s Pletorem");
  });
  it("pracuje > fronta > chyba > spí", () => {
    expect(panel({ ...running, pending: 2, error: "x" }).kind).toBe("working");
    expect(panel({ ...idle, pending: 2, error: "x" }).kind).toBe("queued");
    expect(panel({ ...idle, error: "x" }).kind).toBe("error");
    expect(panel(idle).kind).toBe("sleeping");
  });
});

describe("pomocníci", () => {
  it("časy, jeden řádek a rytmus pollingu", () => {
    expect(elapsed(134_000)).toBe("2:14");
    expect(elapsed(3_734_000)).toBe("1:02:14");
    expect(typical(45_000)).toBe("~45 s");
    expect(typical(200_000)).toBe("~3 min");
    expect(oneLine("a\n  b", 10)).toBe("a b");
    expect(oneLine("abcdefghij", 5)).toBe("abcd…");
    expect(pollMs({ ...idle, running: true })).toBe(WORK_POLL_MS);
    expect(pollMs(null)).toBe(IDLE_POLL_MS);
    expect(pollMs(undefined)).toBe(IDLE_POLL_MS);
  });
});
