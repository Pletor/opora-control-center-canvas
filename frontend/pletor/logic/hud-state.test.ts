import { describe, expect, it } from "vitest";
import { HANDOFF_MS, REPLY_MS, hudLabel, hudState, hudWork, type HudInput } from "./hud-state";

const base: HudInput = { sending: false, voice: "idle", error: false, work: null, repliedAt: null, now: 10_000 };
const sent = [{ type: "heart_message" as const, text: "záměr", ok: true }];

describe("hudState", () => {
  it("bez události čeká", () => {
    expect(hudState(base)).toBe("idle");
  });
  it("odesílání přebije vše, i poslech, čtení a starou chybu", () => {
    expect(hudState({ ...base, sending: true, voice: "listening", error: true, work: "heart" })).toBe("thinking");
    expect(hudState({ ...base, sending: true, voice: "speaking" })).toBe("thinking");
  });
  it("čtení přebije práci srdce, práce přebije poslech", () => {
    expect(hudState({ ...base, voice: "speaking", work: "heart" })).toBe("speaking");
    expect(hudState({ ...base, voice: "listening", work: "handoff" })).toBe("working");
    expect(hudState({ ...base, voice: "listening" })).toBe("listening");
  });
  it("chyba stojí pod přemýšlením a čtením, nad prací", () => {
    expect(hudState({ ...base, error: true, work: "heart" })).toBe("error");
    expect(hudState({ ...base, error: true, voice: "speaking" })).toBe("speaking");
  });
  it("odpověď bez hlasu blikne jako mluvení a po REPLY_MS se vrátí do klidu", () => {
    expect(hudState({ ...base, repliedAt: 10_000 })).toBe("speaking");
    expect(hudState({ ...base, repliedAt: 10_000 - REPLY_MS })).toBe("idle");
  });
});

describe("hudWork", () => {
  it("běžící srdce je práce", () => {
    expect(hudWork({ running: true }, [], null, 0)).toBe("heart");
    expect(hudWork({ running: false }, [], null, 0)).toBeNull();
    expect(hudWork("Spí", [], null, 0)).toBeNull();
  });
  it("předání srdci platí HANDOFF_MS od odpovědi, selhané předání ne", () => {
    expect(hudWork(null, sent, 10_000, 10_000 + HANDOFF_MS - 1)).toBe("handoff");
    expect(hudWork(null, sent, 10_000, 10_000 + HANDOFF_MS)).toBeNull();
    expect(hudWork(null, [{ ...sent[0], ok: false }], 10_000, 10_000)).toBeNull();
    expect(hudWork(null, [{ type: "vault_note", text: "x", ok: true }], 10_000, 10_000)).toBeNull();
  });
});

describe("hudLabel", () => {
  it("přemýšlí, mluví a práce rozliší předání od srdce", () => {
    expect(hudLabel("thinking")).toBe("přemýšlím");
    expect(hudLabel("working", "handoff")).toBe("zadávám srdci");
    expect(hudLabel("working", "heart")).toBe("srdce pracuje");
    expect(hudLabel("speaking")).toBe("mluvím");
  });
});
