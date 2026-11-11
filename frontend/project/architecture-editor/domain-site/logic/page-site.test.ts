import { describe, expect, it } from "vitest";
import type { PageSite } from "@/shared/types/logic/types";
import { MAX_PAGE_SECTIONS, addSection, moveSection, navLabelOf, pageSiteForSave, removeSection, updateSection, withPageIntent } from "./page-site";

describe("úprava sekcí stránky", () => {
  const base: PageSite = { kind: "page", path: "/k" };
  const sec = (id: string) => ({ id, role: "content" as const, name: id, intent: "" });
  const ids = (site: PageSite) => site.sections?.map((s) => s.id);
  it("addSection přidá obsahovou sekci s volným id a nemění vstup", () => {
    expect(addSection(base).sections).toEqual([{ id: "sekce-1", role: "content", name: "Nová sekce", intent: "" }]);
    expect(base).not.toHaveProperty("sections");
    expect(ids(addSection({ ...base, sections: [sec("sekce-1"), sec("sekce-3")] }))).toEqual(["sekce-1", "sekce-3", "sekce-2"]);
  });
  it("addSection na limitu sekcí nic nepřidá", () => {
    const full: PageSite = { ...base, sections: Array.from({ length: MAX_PAGE_SECTIONS }, (_, i) => sec("s" + i)) };
    expect(addSection(full)).toBe(full);
  });
  it("updateSection změní jen zadanou sekci a id nepřepíše", () => {
    const site: PageSite = { ...base, sections: [sec("a"), sec("b")] };
    const next = updateSection(site, "b", { role: "faq", name: "Otázky", id: "x" } as never);
    expect(next.sections?.[1]).toEqual({ id: "b", role: "faq", name: "Otázky", intent: "" });
    expect(next.sections?.[0]).toBe(site.sections?.[0]);
    expect(updateSection(base, "a", { name: "x" })).toBe(base);
  });
  it("removeSection odebere sekci a po poslední vynechá klíč sections", () => {
    const site: PageSite = { ...base, sections: [sec("a"), sec("b")] };
    expect(ids(removeSection(site, "a"))).toEqual(["b"]);
    expect(removeSection(removeSection(site, "a"), "b")).toEqual(base);
    expect(removeSection(site, "nic")).toEqual(site);
  });
  it("moveSection posune o místo a na kraji zůstane", () => {
    const site: PageSite = { ...base, sections: [sec("a"), sec("b"), sec("c")] };
    expect(ids(moveSection(site, "b", -1))).toEqual(["b", "a", "c"]);
    expect(ids(moveSection(site, "b", 1))).toEqual(["a", "c", "b"]);
    expect(moveSection(site, "a", -1)).toBe(site);
    expect(moveSection(site, "c", 1)).toBe(site);
    expect(moveSection(site, "zzz", 1)).toBe(site);
  });
  it("pageSiteForSave ořízne název a záměr sekcí a bez sekcí klíč vynechá", () => {
    const saved = pageSiteForSave({ ...base, sections: [{ id: "a", role: "hero", name: "  Úvod ", intent: "  Zaujmout " }] });
    expect(saved.sections).toEqual([{ id: "a", role: "hero", name: "Úvod", intent: "Zaujmout" }]);
    expect(pageSiteForSave({ ...base, sections: [] })).not.toHaveProperty("sections");
  });
  it("updateSection zapíše moves a pageSiteForSave ho ořízne, prázdné vynechá", () => {
    const site = updateSection({ ...base, sections: [sec("a"), sec("b")] }, "a", { moves: "  Rozptýlí obavu ze spamu. " });
    expect(site.sections?.[0].moves).toBe("  Rozptýlí obavu ze spamu. ");
    const saved = pageSiteForSave(updateSection(site, "b", { moves: "   " }));
    expect(saved.sections?.[0]).toEqual({ ...sec("a"), moves: "Rozptýlí obavu ze spamu." });
    expect(saved.sections?.[1]).toEqual(sec("b"));
    expect(saved.sections?.[1]).not.toHaveProperty("moves");
  });
});

const sections = [{ id: "form", role: "cta" as const, name: "Formulář", intent: "" }];

describe("záměr stránky ve formuláři", () => {
  it("změna cesty ani pole zachová ostatní klíče site včetně sekcí", () => {
    const site: PageSite = { kind: "page", path: "/kontakt", goal: "Poptávka", sections };
    expect(withPageIntent(site, "feel", "klidně")).toEqual({ ...site, feel: "klidně" });
    expect(site).not.toHaveProperty("feel");
  });
  it("při uložení ořízne text, prázdné pole vynechá a nedoplní žádnou výchozí hodnotu", () => {
    const saved = pageSiteForSave({ kind: "page", path: "kontakt", goal: "  Poptávka  ", feel: "   ", navLabel: "", sections });
    expect(saved).toEqual({ kind: "page", path: "/kontakt", goal: "Poptávka", sections });
    expect(pageSiteForSave({ kind: "page", path: "/" })).toEqual({ kind: "page", path: "/" });
  });
  it("při uložení zachová box a parent sekce, parent na odebranou sekci zahodí", () => {
    const boxed: PageSite = { kind: "page", path: "/", sections: [
      { id: "head", role: "header", name: "Hlavička", intent: "", box: { x: 0, y: 0, w: 12, h: 2 } },
      { id: "nav", role: "nav", name: " Menu ", intent: "", box: { x: 0, y: 0, w: 6, h: 1 }, parent: "head" },
      { id: "lost", role: "cta", name: "Výzva", intent: "", parent: "gone" },
    ] };
    expect(pageSiteForSave(boxed).sections).toEqual([
      { id: "head", role: "header", name: "Hlavička", intent: "", box: { x: 0, y: 0, w: 12, h: 2 } },
      { id: "nav", role: "nav", name: "Menu", intent: "", box: { x: 0, y: 0, w: 6, h: 1 }, parent: "head" },
      { id: "lost", role: "cta", name: "Výzva", intent: "" },
    ]);
  });
  it("při uložení zachová stav, zdroj, vzhled a inspiraci boxu; prázdnou inspiraci a vzhled vynechá", () => {
    const site: PageSite = { kind: "page", path: "/", sections: [
      { id: "a", role: "hero", name: "Úvod", intent: "", status: "proposed", source: "scan", look: " tmavé pozadí ", inspiration: { files: ["f1"], url: " https://x.cz ", note: "  barvy " } },
      { id: "b", role: "cta", name: "Výzva", intent: "", status: "approved", look: "  ", inspiration: { files: [], url: " ", note: "" } },
    ] };
    expect(pageSiteForSave(site).sections).toEqual([
      { id: "a", role: "hero", name: "Úvod", intent: "", status: "proposed", source: "scan", look: "tmavé pozadí", inspiration: { files: ["f1"], url: "https://x.cz", note: "barvy" } },
      { id: "b", role: "cta", name: "Výzva", intent: "", status: "approved" },
    ]);
  });
  it("navigace ukazuje popisek v menu, jinak název stránky", () => {
    expect(navLabelOf({ name: "Kontaktní stránka", site: { kind: "page", path: "/k", navLabel: "Kontakt" } })).toBe("Kontakt");
    expect(navLabelOf({ name: "Kontaktní stránka", site: { kind: "page", path: "/k" } })).toBe("Kontaktní stránka");
    expect(navLabelOf({ name: "Doména", site: { kind: "application", environments: [] } })).toBe("Doména");
  });
});
