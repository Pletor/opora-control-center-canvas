import { describe, expect, it } from "vitest";
import type { ApplicationSite } from "@/shared/types/logic/types";
import { journeysOfPage, pageJourneyText } from "./page-journeys";

const site: ApplicationSite = { kind: "application", environments: [], journeys: [
  { id: "kurz", name: "Prodej kurzu", steps: [{ id: "a", page: "nav" }, { id: "b", page: "obsah", label: "Obsah zdarma" }, { id: "c", page: "nabidka" }] },
  { id: "znovu", name: "Návrat", steps: [{ id: "x", page: "nabidka", label: "Prodej" }, { id: "y", page: "obsah" }, { id: "z", page: "nabidka" }] },
] };

describe("stránka zná své cesty", () => {
  it("najde každý krok, který na stránku vede, s rolí a pořadím od 1", () => {
    expect(journeysOfPage(site, "nabidka")).toEqual([
      { journeyId: "kurz", journeyName: "Prodej kurzu", stepId: "c", step: 3 },
      { journeyId: "znovu", journeyName: "Návrat", stepId: "x", step: 1, label: "Prodej" },
      { journeyId: "znovu", journeyName: "Návrat", stepId: "z", step: 3 },
    ]);
    expect(journeysOfPage(site, "jina")).toEqual([]);
    expect(journeysOfPage(undefined, "obsah")).toEqual([]);
  });
  it("popíše roli větou s rolí i bez ní", () => {
    const [withLabel, withoutLabel] = journeysOfPage(site, "obsah");
    expect(pageJourneyText(withLabel)).toBe("Prodej kurzu · Obsah zdarma (krok 2)");
    expect(pageJourneyText(withoutLabel)).toBe("Návrat · krok 2");
  });
});
