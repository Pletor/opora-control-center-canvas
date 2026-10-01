import { describe, expect, it } from "vitest";
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import { fitReason, fitWords, fitsProfile, outsideSummary, splitByProfile, type Fittable } from "./catalog-fit";
import { CATALOG_ITEMS } from "./library-catalog";
import { AGENT_ITEMS } from "@/editor/component-library/agent-catalog/logic/agent-catalog";
import { ARCHITECTURE_OPTIONS, TENANCY_OPTIONS } from "@/shared/project-capabilities/logic/project-profile";

const profile = (architecture: ProjectProfile["architecture"], tenancy: ProjectProfile["tenancy"]): ProjectProfile => ({ architecture, tenancy, platform: "web" });
const universal: Fittable & { id: string } = { id: "u" };
const multi: Fittable & { id: string } = { id: "m", fits: { tenancy: ["multi"] } };
const gateway: Fittable & { id: string } = { id: "g", fits: { architecture: ["microservices"] } };
const boundary: Fittable & { id: string } = { id: "b", fits: { architecture: ["modular"] } };

describe("catalog-fit – kam prvek patří", () => {
  it("prvek bez fits patří všem", () => {
    expect(fitsProfile(universal, profile("microservices", "multi"))).toBe(true);
    expect(fitReason(universal, profile("microservices", "multi"))).toBeNull();
  });

  it("nenastavený profil nic neschová a nic nezdůvodní", () => {
    const empty = profile("", "");
    expect(splitByProfile([universal, multi, gateway], empty)).toEqual({ fitting: [universal, multi, gateway], outside: [] });
    expect(fitReason(multi, empty)).toBeNull();
  });

  it("nenastavené pole profilu podle sebe nefiltruje", () => {
    expect(fitsProfile(gateway, profile("", "multi"))).toBe(true);
    expect(fitsProfile(multi, profile("modular", ""))).toBe(true);
    expect(fitReason(multi, profile("modular", ""))).toBeNull();
  });

  it("multitenantní modulární projekt vidí multitenanci a hranice modulu, API gateway je mimo profil", () => {
    const { fitting, outside } = splitByProfile([universal, multi, gateway, boundary], profile("modular", "multi"));
    expect(fitting.map((item) => item.id)).toEqual(["u", "m", "b"]);
    expect(outside.map((item) => item.id)).toEqual(["g"]);
  });

  it("důvod říká, která hodnota profilu prvek přivedla", () => {
    expect(fitReason(multi, profile("modular", "multi"))).toBe("kvůli profilu: multitenant");
    expect(fitReason(boundary, profile("modular", "multi"))).toBe("kvůli profilu: modulární monolit");
    expect(fitReason({ fits: { architecture: ["modular"], tenancy: ["multi"] } }, profile("modular", "multi"))).toBe("kvůli profilu: modulární monolit, multitenant");
    expect(fitReason(gateway, profile("modular", "multi"))).toBeNull();
  });

  it("řádek mimo profil řekne počet a pro koho prvky jsou", () => {
    expect(fitWords(gateway)).toEqual(["mikroslužby"]);
    expect(outsideSummary([gateway, { fits: { architecture: ["serverless"] } }], ["prvek", "prvky", "prvků"])).toBe("2 prvky (mikroslužby, serverless)");
    expect(outsideSummary([gateway, gateway, gateway, gateway, gateway], ["prvek", "prvky", "prvků"])).toBe("5 prvků (mikroslužby)");
  });
});

describe("catalog-fit – vydané katalogy", () => {
  const modularMulti = profile("modular", "multi");
  const library = splitByProfile(CATALOG_ITEMS, modularMulti);
  const agents = splitByProfile(AGENT_ITEMS, modularMulti);

  it("Knihovna: multitenance a hranice modulu jsou ve výběru, API gateway ne", () => {
    const fitting = library.fitting.map((item) => item.id);
    expect(fitting).toEqual(expect.arrayContaining(["tenant-request-context", "tenant-data-isolation", "tenant-config-limits", "be-module-boundary"]));
    expect(library.outside.map((item) => item.id)).toContain("ms-api-gateway");
  });

  it("Agenti: saga přes služby je mimo profil modulárního monolitu", () => {
    expect(agents.outside.map((item) => item.id)).toEqual(["wf-saga-across-services"]);
  });

  it("architektonická pravidla jsou invarianty prvků Knihovny, ke kterým patří", () => {
    const invariants = (id: string) => library.fitting.find((item) => item.id === id)?.invariants.map((rule) => rule.text) ?? [];
    expect(invariants("tenant-data-isolation").join(" ")).toContain("filtruje podle tenanta");
    expect(invariants("be-module-boundary").length).toBe(2);
  });

  it("každé fits míří na známou hodnotu profilu a nikdy není prázdné", () => {
    const known = new Set([...ARCHITECTURE_OPTIONS, ...TENANCY_OPTIONS].map((option) => option.word));
    for (const item of [...CATALOG_ITEMS, ...AGENT_ITEMS]) {
      if (!item.fits) continue;
      expect(fitWords(item).length, item.id).toBeGreaterThan(0);
      expect(fitWords(item).filter((word) => !known.has(word)), item.id).toEqual([]);
    }
  });
});
