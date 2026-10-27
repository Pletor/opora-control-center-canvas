import { describe, expect, it } from "vitest";
import { derivedForDomain, derivedJourneysUrl, derivedJourneyText, normalizeDerivedJourneys } from "./derived-journeys";

describe("odvozené cesty zákazníka", () => {
  it("adresa dotazu nese projekt", () => {
    expect(derivedJourneysUrl("p 1")).toBe("/api/project-architecture/journeys?project=p+1");
  });
  it("čte řadu kroků i důvod přerušení a vadné položky zahodí", () => {
    const raw = { journeys: [
      { applicationId: "app", id: "poptavka", name: "Poptávka", from: "nav", to: "dik", steps: [], line: "nav → /kontakt[form] → /dekujeme" },
      { applicationId: "app", id: "pryc", name: "Pryč", from: "nav", to: "x", broken: "chybí stránka x, kam cesta vede." },
      { applicationId: "app", id: "bez" }, { id: "sirotek", line: "nav → /" }, null, "x",
    ] };
    expect(normalizeDerivedJourneys(raw)).toEqual([
      { applicationId: "app", id: "poptavka", line: "nav → /kontakt[form] → /dekujeme" },
      { applicationId: "app", id: "pryc", broken: "chybí stránka x, kam cesta vede." },
    ]);
    expect(normalizeDerivedJourneys(null)).toEqual([]);
    expect(normalizeDerivedJourneys({ journeys: "x" })).toEqual([]);
  });
  it("vybere cesty jedné domény podle id", () => {
    const items = [{ applicationId: "a", id: "j", line: "nav → /a" }, { applicationId: "b", id: "j", line: "nav → /b" }];
    expect(derivedForDomain(items, "b").get("j")?.line).toBe("nav → /b");
    expect(derivedForDomain(items, "c").size).toBe(0);
  });
  it("u cesty ukáže řadu kroků, přerušení s důvodem, nebo nic", () => {
    expect(derivedJourneyText({ applicationId: "a", id: "j", line: "nav → /" })).toEqual({ text: "nav → /", broken: false });
    expect(derivedJourneyText({ applicationId: "a", id: "j", broken: "chybí stránka x, kam cesta vede." }))
      .toEqual({ text: "cesta je přerušená: chybí stránka x, kam cesta vede.", broken: true });
    expect(derivedJourneyText(undefined)).toBeNull();
  });
});
