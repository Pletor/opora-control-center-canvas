import { describe, expect, it } from "vitest";
import type { CanvasNode } from "@/shared/types/logic/types";
import { DOMAIN_KIND_LABEL, domainKind, domainKindOf, environmentAddress, isMobileDomain } from "./domain-kind";

describe("domainKind", () => {
  it("rozpozná aplikaci podle app.", () => expect(domainKind("app.tajemstviopory.cz")).toBe("app"));
  it("rozpozná administraci podle admin / admins", () => {
    expect(domainKind("admins.tajemstviopory.cz")).toBe("admin");
    expect(domainKind("admin.example.cz")).toBe("admin");
  });
  it("jinak je to web", () => {
    expect(domainKind("tajemstviopory.cz")).toBe("web");
    expect(domainKind("")).toBe("web");
    expect(domainKind("application.example.cz")).toBe("web");
  });
  it("ignoruje velikost písmen a mezery", () => expect(domainKind(" APP.Example.cz ")).toBe("app"));
});

describe("domainKindOf", () => {
  const app = (name: string, environments: { name: string; host: string }[]): CanvasNode =>
    ({ id: "d", parentId: null, kind: "sector", name, purpose: "", x: 0, y: 0, site: { kind: "application", environments } });
  it("bere host prostředí před jménem uzlu", () => expect(domainKindOf(app("web", [{ name: "Produkce", host: "app.example.cz" }]))).toBe("app"));
  it("bez prostředí se druh odvodí z jména uzlu", () => {
    expect(domainKindOf(app("app.tajemstviopory.cz", []))).toBe("app");
    expect(domainKindOf(app("tajemstviopory.cz", []))).toBe("web");
  });
});

describe("mobilní aplikace", () => {
  const mobile = (platform: "android" | "ios" | "web"): CanvasNode =>
    ({ id: "m", parentId: null, kind: "sector", name: "app.example.cz", purpose: "", x: 0, y: 0,
      site: { kind: "application", platform, environments: [{ name: "Produkce", bundleId: "cz.example.app" }] } });
  it("platforma má přednost před hostem i jménem", () => {
    expect(domainKindOf(mobile("android"))).toBe("android");
    expect(domainKindOf(mobile("ios"))).toBe("ios");
    expect(domainKindOf(mobile("web"))).toBe("app");
    expect(DOMAIN_KIND_LABEL.android).toBe("Aplikace Android");
    expect(DOMAIN_KIND_LABEL.ios).toBe("Aplikace iOS");
  });
  it("mobilní doména nemá host, adresou prostředí je bundle ID", () => {
    expect(isMobileDomain(mobile("ios"))).toBe(true);
    expect(isMobileDomain(mobile("web"))).toBe(false);
    expect(environmentAddress({ name: "Produkce", bundleId: "cz.example.app" })).toBe("cz.example.app");
    expect(environmentAddress({ name: "Produkce", host: "www.example.cz" })).toBe("www.example.cz");
    expect(environmentAddress(undefined)).toBe("");
  });
});
