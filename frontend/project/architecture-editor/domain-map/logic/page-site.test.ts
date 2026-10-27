import { describe, expect, it } from "vitest";
import type { PageSite } from "@/shared/types/logic/types";
import { navLabelOf, pageSiteForSave, withPageIntent } from "./page-site";

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
  it("navigace ukazuje popisek v menu, jinak název stránky", () => {
    expect(navLabelOf({ name: "Kontaktní stránka", site: { kind: "page", path: "/k", navLabel: "Kontakt" } })).toBe("Kontakt");
    expect(navLabelOf({ name: "Kontaktní stránka", site: { kind: "page", path: "/k" } })).toBe("Kontaktní stránka");
    expect(navLabelOf({ name: "Doména", site: { kind: "application", environments: [] } })).toBe("Doména");
  });
});
