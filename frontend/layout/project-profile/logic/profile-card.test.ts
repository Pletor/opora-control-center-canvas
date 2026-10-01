import { describe, expect, it } from "vitest";
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import { chooseArchitecture, chooseTenancy, draftChanged, draftOf } from "./profile-card";

const saved: ProjectProfile = { architecture: "", tenancy: "", platform: "web" };

describe("profile-card – rozepsaná volba", () => {
  it("volba se vybere, druhý klik ji zruší", () => {
    const one = chooseArchitecture(draftOf(saved), "modular");
    expect(one).toEqual({ architecture: "modular", tenancy: "" });
    expect(chooseArchitecture(one, "modular").architecture).toBe("");
    expect(chooseArchitecture(one, "microservices").architecture).toBe("microservices");
    expect(chooseTenancy(one, "multi")).toEqual({ architecture: "modular", tenancy: "multi" });
  });

  it("uložit jde jen změnu", () => {
    expect(draftChanged(draftOf(saved), saved)).toBe(false);
    expect(draftChanged({ architecture: "modular", tenancy: "multi" }, saved)).toBe(true);
    expect(draftChanged({ architecture: "", tenancy: "" }, { ...saved, tenancy: "multi" })).toBe(true);
  });
});
