import { describe, expect, it } from "vitest";
import type { PageSection } from "@/shared/types/logic/types";
import { fitVia, sectionsOfPage, viaActions, viaForSave, viaSentence } from "./journey-via";

const sections: PageSection[] = [{ id: "cta", role: "cta", name: "Výzva", intent: "" }, { id: "form", role: "form", name: "Formulář", intent: "" }];

describe("signál přechodu do kroku", () => {
  it("první krok smí jen otevřít stránku, další jen kliknout nebo odeslat", () => {
    expect(viaActions(0).map((item) => item.value)).toEqual(["open"]);
    expect(viaActions(2).map((item) => item.value)).toEqual(["click", "submit"]);
    expect(fitVia(0, { do: "click", section: "cta" })).toBeUndefined();
    expect(fitVia(0, { do: "open", text: "x" })).toEqual({ do: "open" });
    expect(fitVia(1, { do: "open" })).toBeUndefined();
    const via = { do: "submit" as const, section: "form" };
    expect(fitVia(1, via)).toBe(via);
    expect(fitVia(1, undefined)).toBeUndefined();
  });
  it("před uložením ořízne text a prázdnou sekci i text vynechá", () => {
    expect(viaForSave({ do: "click", section: " ", text: "  Chci video " })).toEqual({ do: "click", text: "Chci video" });
    expect(viaForSave({ do: "submit", section: "form", text: "" })).toEqual({ do: "submit", section: "form" });
  });
  it("sekce bere jen ze stránky; menu a chybějící stránka sekce nemají", () => {
    const pages = [{ id: "kontakt", site: { kind: "page" as const, path: "/kontakt", sections } }, { id: "app", site: undefined }];
    expect(sectionsOfPage("kontakt", pages)).toBe(sections);
    expect(sectionsOfPage("nav", pages)).toEqual([]);
    expect(sectionsOfPage("app", pages)).toEqual([]);
    expect(sectionsOfPage(null, pages)).toEqual([]);
  });
  it("čte se jako věta s názvem sekce a sekci, kterou stránka nemá, jmenuje jen id", () => {
    expect(viaSentence({ do: "submit", section: "cta" }, sections)).toEqual({ text: "odešle formulář v sekci Výzva", missingSection: null });
    expect(viaSentence({ do: "click", section: "form", text: "Chci video" }, sections).text).toBe("klikne na „Chci video“ v sekci Formulář");
    expect(viaSentence({ do: "submit", text: "Odeslat" }, sections).text).toBe("odešle formulář „Odeslat“");
    expect(viaSentence({ do: "click" }, [])).toEqual({ text: "klikne", missingSection: null });
    expect(viaSentence({ do: "open" }, sections).text).toBe("otevře stránku přímo");
    expect(viaSentence({ do: "click", section: "smazana" }, sections)).toEqual({ text: "klikne v sekci smazana", missingSection: "smazana" });
  });
});
