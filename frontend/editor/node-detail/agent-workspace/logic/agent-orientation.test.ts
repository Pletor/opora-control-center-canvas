import { describe, expect, it } from "vitest";
import { orientationSearch, orientationSummary } from "./agent-orientation";

const brief = {
  orientation: {
    scope: { nodeId: "focus", path: ["Sektor", "Ohnisko"], readOnly: true },
    goal: { goal: "Dodat UI", nonGoals: "Bez zápisu", acceptance: "Test zelený", status: "present" },
    materials: [{ id: "m1", caption: "Specifikace", path: "spec.md", sourceNodeId: "sektor", status: "present" }],
    contextGaps: [{ id: "handoff", label: "Chybí předávka", instruction: "Vyžádejte si ji.", status: "missing" }],
    nextAction: { kind: "request-context", label: "Vyžádejte si ji.", status: "recommendation" },
  },
  blocks: [],
  communication: { incoming: { messages: [{ id: "msg-1", body: "Přečti Specifikace", senderLabel: "agent", receipt: null }], hasMore: false, nextBefore: null }, outgoing: { messages: [], hasMore: false, nextBefore: null } },
};

describe("agent-orientation", () => {
  it("vrátí krátké karty z autoritativní orientace bez domýšlení", () => {
    expect(orientationSummary(brief).goal).toBe("Dodat UI");
    expect(orientationSummary(brief).nextAction).toBe("Vyžádejte si ji.");
    expect(orientationSummary(brief).readOnly).toBe(true);
  });

  it("hranice z odkazu orientace čte z horního pole briefu, starší kopii ponechá", () => {
    const boundaries = { effectiveRules: [], proposedRules: [{ id: "r1" }], nonGoals: "Bez zápisu" };
    const linked = { ...brief, boundaries, orientation: { ...brief.orientation, boundaries: { ref: "boundaries" } } };
    expect(orientationSummary(linked).boundaries).toEqual(boundaries);
    const copied = { ...brief, orientation: { ...brief.orientation, boundaries: { nonGoals: "Kopie" } } };
    expect(orientationSummary(copied).boundaries).toEqual({ nonGoals: "Kopie" });
  });

  it("vyhledává pouze ve skutečně načteném briefu včetně zpráv", () => {
    expect(orientationSearch(brief, "specifikace")).toEqual([
      { id: "material:m1", label: "Specifikace", source: "Podklad · sektor" },
      { id: "message:msg-1", label: "Přečti Specifikace", source: "Příchozí zpráva · agent" },
    ]);
    expect(orientationSearch(brief, "nenalezeno")).toEqual([]);
  });

  it("vrátí nalezený blok s jeho identitou, číslem a názvem", () => {
    const withBlock = { ...brief, blocks: [{ id: "block-ui", number: "7", title: "Rozhraní agenta", text: "Vyhledání v editoru" }] };
    expect(orientationSearch(withBlock, "vyhledání")).toEqual([
      { id: "block:block-ui", label: "7 · Rozhraní agenta", source: "Blok 7" },
    ]);
  });
});
