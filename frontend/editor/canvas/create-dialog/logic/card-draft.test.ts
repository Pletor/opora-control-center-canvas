import { describe, expect, it } from "vitest";
import { agentSummary, cardDraftOf, emptyCard, sameCardDraft, toggleLayer } from "./card-draft";

describe("rozepsaná karta", () => {
  it("chybějící klíče jsou prázdné a porovnání vidí změnu", () => {
    expect(cardDraftOf(undefined)).toEqual({ layer: "", status: "", due: "", model: "", effort: "" });
    const draft = cardDraftOf({ layer: "backend", due: "2026-10-10" });
    expect(draft).toEqual({ layer: "backend", status: "", due: "2026-10-10", model: "", effort: "" });
    expect(sameCardDraft(draft, cardDraftOf({ layer: "backend", due: "2026-10-10" }))).toBe(true);
    expect(sameCardDraft(draft, { ...draft, status: "ready" })).toBe(false);
  });

  it("čip vrstvy vybere, druhý klik na tentýž výběr zruší, jiný ho přepne", () => {
    const fe = toggleLayer(emptyCard(), "frontend");
    expect(fe.layer).toBe("frontend");
    expect(toggleLayer(fe, "frontend").layer).toBe("");
    expect(toggleLayer(fe, "library").layer).toBe("library");
  });
});

describe("souhrn sekce Pro agenta", () => {
  it("ukáže jen vyplněné hodnoty, model a effort jako dvojici", () => {
    expect(agentSummary(emptyCard())).toBe("");
    expect(agentSummary({ ...emptyCard(), status: "ready", model: "sonnet", effort: "medium" })).toBe("ready · sonnet/medium");
    expect(agentSummary({ ...emptyCard(), effort: "high", due: "2026-10-10" })).toBe("high · 2026-10-10");
    // Vrstva do souhrnu nepatří: má vlastní řadu čipů nad sekcí.
    expect(agentSummary({ ...emptyCard(), layer: "frontend", model: "opus" })).toBe("opus");
  });
});
