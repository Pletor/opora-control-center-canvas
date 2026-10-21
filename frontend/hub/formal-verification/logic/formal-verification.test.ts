import { describe, expect, it } from "vitest";
import { parseFormalHistory, parseFormalRecord } from "./formal-verification-parse";
import { formalArtifactUrl, formalDetailUrl, formalRevision, formalSourceUrl } from "./formal-verification";
import { formalFixture, formalScope } from "./formal-verification-fixtures";

describe("formal evidence remains untrusted and scoped", () => {
  it("accepts the exact public record and drops private unknown fields", () => {
    const record = formalFixture();
    expect(parseFormalRecord(record, formalScope, record.id)).toEqual(record);
    const parsed = parseFormalRecord({ ...record, token: "PRIVATE-capability", ownerNonce: "PRIVATE-owner",
      verification: { ...record.verification, tool: { ...record.verification.tool, token: "PRIVATE-tool" } } }, formalScope);
    expect(JSON.stringify(parsed)).not.toContain("PRIVATE");
    expect(parsed.currentEligibility).toBe(false);
    expect(parsed.report?.independentlyVerified).toBe(false);
  });
  it.each([{ trust: "independently-verified" }, { independentlyVerified: true }, { currentEligibility: true }, { sourceBinding: "github-verified" }])("rejects forged request trust %j", patch => {
    expect(() => parseFormalRecord({ ...formalFixture(), ...patch }, formalScope)).toThrow(/důvěry/);
  });
  it.each([{ trust: "verified" }, { independentlyVerified: true }, { currentEligibility: true }, { sourceBinding: "verified" }])("rejects forged report trust %j", patch => {
    const record = formalFixture();
    expect(() => parseFormalRecord({ ...record, report: { ...record.report, ...patch } }, formalScope)).toThrow();
  });
  it("accepts consistent ci-verified trust but never a mixed or eligible one", () => {
    const record = formalFixture(), ci = { trust: "ci-verified", sourceBinding: "ci-verified" };
    const parsed = parseFormalRecord({ ...record, ...ci, report: { ...record.report, ...ci } }, formalScope);
    expect(parsed.trust).toBe("ci-verified");
    expect(parsed.report!.trust).toBe("ci-verified");
    expect(parsed.independentlyVerified).toBe(false);
    expect(() => parseFormalRecord({ ...record, trust: "ci-verified" }, formalScope)).toThrow(/důvěry/);
    expect(() => parseFormalRecord({ ...record, ...ci, currentEligibility: true }, formalScope)).toThrow(/důvěry/);
  });
  it("accepts reported run metadata without upgrading trust", () => {
    const record = formalFixture();
    record.report!.artifacts.push({ path: "run-metadata.json", role: "run-metadata", sha256: "7".repeat(64), bytes: 240, available: true });
    const parsed = parseFormalRecord(record, formalScope);
    expect(parsed.report!.artifacts.at(-1)?.role).toBe("run-metadata");
    expect(parsed.report!.trust).toBe("agent-reported");
    expect(parsed.report!.independentlyVerified).toBe(false);
    expect(parsed.currentEligibility).toBe(false);
  });
  it("rejects foreign scopes and a response for another selected ID", () => {
    const record = formalFixture();
    expect(() => parseFormalRecord(record, { ...formalScope, workspace: "other" })).toThrow();
    expect(() => parseFormalRecord(record, formalScope, "f".repeat(32))).toThrow();
  });
  it("requires complete claim coverage for passed, unique IDs and matching tool claim kinds", () => {
    const record = formalFixture();
    expect(() => parseFormalRecord({ ...record, report: { ...record.report, checkedClaims: [] } }, formalScope)).toThrow();
    expect(() => parseFormalRecord({ ...record, report: { ...record.report, checkedClaims: ["foreign"] } }, formalScope)).toThrow();
    expect(() => parseFormalRecord({ ...record, verification: { ...record.verification, claims: [record.verification.claims[0], record.verification.claims[0]] } }, formalScope)).toThrow();
    expect(() => parseFormalRecord({ ...record, verification: { ...record.verification, tool: { ...record.verification.tool, name: "lean" } } }, formalScope)).toThrow();
    const lean = { ...record, verification: { ...record.verification, tool: { ...record.verification.tool, name: "lean" }, claims: [{ ...record.verification.claims[0], kind: "theorem" }] } };
    expect(parseFormalRecord(lean, formalScope).verification.tool.name).toBe("lean");
  });
  it("bounds configurations and refuses malformed artifact paths and roles", () => {
    const record = formalFixture(), artifact = record.verification.artifacts[0];
    for (const patch of [{ path: "../secret" }, { path: "C:\\secret" }, { path: "/absolute" }, { path: "a//b" }, { path: "a/./b" },
      { role: "html-executable" }, { sha256: "bad" }, { bytes: 2 * 1024 * 1024 + 1 }, { available: "yes" }])
      expect(() => parseFormalRecord({ ...record, verification: { ...record.verification, artifacts: [{ ...artifact, ...patch }] } }, formalScope)).toThrow();
    let deep: object = { value: true }; for (let i = 0; i < 10; i++) deep = { child: deep };
    for (const configuration of [deep, { bad: Infinity }, { value: "x".repeat(17000) }, []])
      expect(() => parseFormalRecord({ ...record, verification: { ...record.verification, configuration } }, formalScope)).toThrow();
    expect(() => parseFormalRecord({ ...record, verification: { ...record.verification, artifacts: [artifact, artifact] } }, formalScope)).toThrow();
  });
  it("bounds history and does not silently drop corrupt or duplicate records", () => {
    const record = formalFixture();
    expect(parseFormalHistory({ requests: [] }, formalScope)).toEqual([]);
    expect(() => parseFormalHistory({ requests: [record, record] }, formalScope)).toThrow();
    expect(() => parseFormalHistory({ requests: Array.from({ length: 101 }, () => record) }, formalScope)).toThrow();
    expect(() => parseFormalHistory({ requests: [{ ...record, independentlyVerified: true }] }, formalScope)).toThrow();
  });
  it("never calls unknown current revision stale and never calls a matching record verified", () => {
    const record = formalFixture();
    expect(formalRevision(record, null)).toContain("není známé");
    expect(formalRevision(record, record.acceptedRevision)).toContain("nezávislé ověření není doloženo");
    expect(formalRevision(record, "9".repeat(40))).toContain("Historický");
  });
  it("constructs only scoped artifact URLs and safe reported-source GitHub links", () => {
    const record = formalFixture(), scope = { project: "project&foreign=true", workspace: "w /?#" };
    const url = new URL(formalArtifactUrl(scope, record.id, "1".repeat(64)), "https://canvas.invalid");
    expect(url.origin).toBe("https://canvas.invalid");
    expect([...url.searchParams.keys()]).toEqual(["project", "workspace"]);
    expect(url.searchParams.get("workspace")).toBe(scope.workspace);
    expect(() => formalDetailUrl(formalScope, "../secret")).toThrow();
    expect(() => formalArtifactUrl(formalScope, record.id, "../secret")).toThrow();
    expect(formalSourceUrl("javascript:alert(1)", "1".repeat(40))).toBeNull();
    expect(formalSourceUrl("../repo", "1".repeat(40))).toBeNull();
    expect(formalSourceUrl("owner/..", "1".repeat(40))).toBeNull();
    expect(formalSourceUrl("owner_name/repo", "1".repeat(40))).not.toBeNull();
    expect(formalSourceUrl("owner/repo..name", "1".repeat(40))).toBe(`https://github.com/owner/repo..name/commit/${"1".repeat(40)}`);
  });
});
