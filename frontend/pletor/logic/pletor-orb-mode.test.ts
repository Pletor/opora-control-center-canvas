import { describe, expect, it } from "vitest";
import { REPLY_MS, orbMode } from "./pletor-orb-mode";

const base = { sending: false, error: false, lastPletorAt: null, now: 10_000 };

describe("orbMode", () => {
  it("bez události jádro dýchá", () => {
    expect(orbMode(base)).toBe("idle");
  });
  it("při čekání na odpověď přemýšlí", () => {
    expect(orbMode({ ...base, sending: true })).toBe("thinking");
  });
  it("chyba přebije přemýšlení i záblesk", () => {
    expect(orbMode({ ...base, sending: true, error: true, lastPletorAt: 10_000 })).toBe("error");
  });
  it("čerstvá odpověď blikne a po REPLY_MS se vrátí do dýchání", () => {
    expect(orbMode({ ...base, lastPletorAt: 10_000 })).toBe("reply");
    expect(orbMode({ ...base, lastPletorAt: 10_000 - REPLY_MS + 1 })).toBe("reply");
    expect(orbMode({ ...base, lastPletorAt: 10_000 - REPLY_MS })).toBe("idle");
  });
  it("nové odesílání přebije záblesk předchozí odpovědi", () => {
    expect(orbMode({ ...base, sending: true, lastPletorAt: 10_000 })).toBe("thinking");
  });
});
