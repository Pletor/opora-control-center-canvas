import { describe, expect, it } from "vitest";
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import { CATALOG_ITEMS } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { libraryView } from "./library-scope";

const modularMulti: ProjectProfile = { architecture: "modular", tenancy: "multi", platform: "web" };
const fitting = { scope: "fitting" as const, showOutside: false, query: "" };

describe("library-scope – Knihovna pro profil projektu", () => {
  it("multitenantní modulární projekt vidí Multitenanci nahoře se štítkem a hranici modulu, API gateway je schovaná", () => {
    const view = libraryView(CATALOG_ITEMS, modularMulti, fitting);
    expect(view.categories[0].id).toBe("tenancy");
    expect(view.profileOnly.has("tenancy")).toBe(true);
    expect(view.profileOnly.has("backend")).toBe(false);
    expect(view.notes["be-module-boundary"]).toBe("kvůli profilu: modulární monolit");
    expect(view.shown.some((item) => item.id === "ms-api-gateway")).toBe(false);
    expect(view.hidden.some((item) => item.id === "ms-api-gateway")).toBe(true);
    expect(view.fittingCount).toBeLessThan(view.allCount);
  });

  it("hledání najde API gateway i mimo profil a označí ji", () => {
    const view = libraryView(CATALOG_ITEMS, modularMulti, { ...fitting, query: "gateway" });
    expect(view.shown.map((item) => item.id)).toEqual(["ms-api-gateway"]);
    expect(view.notes["ms-api-gateway"]).toBe("mimo profil");
    expect(view.outsideIds.has("ms-api-gateway")).toBe(true);
  });

  it("nenastavený profil ukáže celý katalog bez poznámek a v pořadí kategorií", () => {
    const view = libraryView(CATALOG_ITEMS, { architecture: "", tenancy: "", platform: "web" }, fitting);
    expect(view.shown).toHaveLength(CATALOG_ITEMS.length);
    expect(view.notes).toEqual({});
    expect(view.categories[0].id).toBe("fe-components");
  });
});
