import { describe, expect, it } from "vitest";
import type { ApplicationSite } from "@/shared/types/logic/types";
import { addressValue, applicationSiteForSave, withAddress, withPlatform } from "./site-platform";

const web: ApplicationSite = { kind: "application", healthPath: "/api/health", environments: [{ name: "Produkce", host: "app.example.cz" }] };

describe("site-platform", () => {
  it("přepnutí na Android vymění host za prázdné bundle ID a zahodí healthPath", () => {
    const android = withPlatform(web, "android");
    expect(android).toEqual({ kind: "application", platform: "android", environments: [{ name: "Produkce", bundleId: "" }] });
    expect(addressValue(android, android.environments[0])).toBe("");
  });
  it("návrat na web uloží doménu bez pole platform", () => {
    const back = withPlatform(withPlatform(web, "ios"), "web");
    expect(back).toEqual({ kind: "application", environments: [{ name: "Produkce", host: "" }] });
    expect(withPlatform(web, "web")).toEqual(web);
  });
  it("adresa se píše do pole platformy a při uložení se ořízne", () => {
    const ios = withAddress(withPlatform(web, "ios"), 0, " cz.example.app ");
    expect(addressValue(ios, ios.environments[0])).toBe(" cz.example.app ");
    expect(applicationSiteForSave({ ...ios, environments: [{ ...ios.environments[0], name: " Produkce " }] }).environments)
      .toEqual([{ name: "Produkce", bundleId: "cz.example.app" }]);
    expect(applicationSiteForSave(withAddress(web, 0, " www.example.cz ")).environments).toEqual([{ name: "Produkce", host: "www.example.cz" }]);
  });
});
