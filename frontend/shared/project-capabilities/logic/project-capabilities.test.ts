import { describe, expect, it } from "vitest";
import { isLocalKind, projectCapabilities } from "./project-capabilities";

const project = (sourceKind?: string) => ({ id: "p1", name: "P", url: null, branch: null, sourceKind });

describe("projectCapabilities", () => {
  it("vestavěný draft je lokální s volnými uzly", () => {
    expect(projectCapabilities("draft", undefined)).toEqual({ localProject: true, legacyFree: true, defaultWorkspace: "draft" });
  });
  it("draft s jiným druhem zdroje ztrácí volné uzly, ale zůstává lokální", () => {
    expect(projectCapabilities("draft", { ...project("local"), id: "draft" }).legacyFree).toBe(false);
    expect(projectCapabilities("draft", { ...project("local"), id: "draft" }).localProject).toBe(true);
  });
  it("lokální a prázdný projekt otevírají návrh, git projekt main", () => {
    expect(projectCapabilities("p1", project("local")).defaultWorkspace).toBe("draft");
    expect(projectCapabilities("p1", project("empty")).defaultWorkspace).toBe("draft");
    expect(projectCapabilities("p1", project("git"))).toEqual({ localProject: false, legacyFree: false, defaultWorkspace: "main" });
  });
  it("neznámý projekt bez druhu zdroje se chová jako git projekt", () => {
    expect(projectCapabilities("p1", undefined).localProject).toBe(false);
  });
  it("isLocalKind zná jen tři lokální druhy", () => {
    expect(["local", "empty", "builtin"].every(isLocalKind)).toBe(true);
    expect(isLocalKind("git")).toBe(false);
    expect(isLocalKind(undefined)).toBe(false);
  });
});
