import { describe, expect, it } from "vitest";
import { overviewCards, voiceName } from "./overview-cards";
import { CLAUDE_BRAIN, type PletorState } from "@/agi-pletor/hud/logic/pletor-client";

const state: PletorState = {
  messages: [{ role: "human", text: "ahoj", at: "" }, { role: "pletor", text: "x".repeat(200), at: "" }],
  heart: "srdce spí", escalations: [{}], brain: CLAUDE_BRAIN,
};

describe("overview-cards", () => {
  it("bez stavu ukáže pomlčky", () => {
    const cards = overviewCards(null, "Prohlížeč");
    expect(cards.map((c) => c.id)).toEqual(["mozek", "srdce", "eskalace", "hlas", "zprava"]);
    expect(cards[0].value).toBe("—");
  });
  it("mapuje stav na karty", () => {
    const cards = overviewCards(state, "Brian");
    expect(cards[0]).toMatchObject({ value: "Claude Sonnet 5.5", note: "cloud · předplatné" });
    expect(cards[1].value).toBe("srdce spí");
    expect(cards[2].value).toBe("1 čekající eskalace");
    expect(cards[4].value.length).toBe(140);
    expect(cards[4].note).toBe("Pletor");
  });
  it("bez zpráv řekne, že rozhovor chybí", () => {
    expect(overviewCards({ ...state, messages: [] }, "x")[4].value).toBe("Zatím bez rozhovoru");
  });
  it("bez hlasů čte prohlížeč", () => expect(voiceName(null, [])).toBe("Prohlížeč"));
});
