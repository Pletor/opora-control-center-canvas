import { describe, expect, it } from "vitest";
import { ARCHITECTURE_OPTIONS, TENANCY_OPTIONS, architectureWord, profileWords, tenancyWord } from "./project-profile";

describe("project-profile – profil slovy", () => {
  it("volby pokrývají přesně hodnoty, které přijme backend", () => {
    expect(ARCHITECTURE_OPTIONS.map((option) => option.id)).toEqual(["monolith", "modular", "microservices", "serverless"]);
    expect(TENANCY_OPTIONS.map((option) => option.id)).toEqual(["single", "multi"]);
  });

  it("hlavička řekne platformu, architekturu i uživatele", () => {
    expect(profileWords({ platform: "web", architecture: "modular", tenancy: "multi" })).toBe("Web · Modulární monolit · Multitenant");
    expect(profileWords({ platform: "app", architecture: "", tenancy: "single" })).toBe("Aplikace · Jeden tenant");
  });

  it("nenastavený profil to přizná, místo aby mlčel", () => {
    expect(profileWords({ platform: "web", architecture: "", tenancy: "" })).toBe("Web · profil nenastaven");
  });

  it("slova do důvodu jsou malými písmeny", () => {
    expect(architectureWord("microservices")).toBe("mikroslužby");
    expect(tenancyWord("multi")).toBe("multitenant");
  });
});
