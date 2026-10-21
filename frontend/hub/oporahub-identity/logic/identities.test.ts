import { describe, expect, it } from "vitest";
import { evidenceUrl, identityError, parseIdentities, publicIdentities } from "./identities";

const row = (over: Record<string, unknown> = {}) => ({ identityId: "id_1", name: "Martin", githubLogin: "pletor", githubUserId: null,
  state: "claimed", operator: true, claimedAt: "2026-10-20T10:00:00Z", verifiedAt: null, revokedAt: null, evidence: null,
  marker: "Opora-Identity: id_1 abc123", ...over });

describe("identity registry", () => {
  it("parses items and keeps the marker only in memory", () => {
    const items = parseIdentities({ items: [row(), row({ identityId: "id_2", state: "verified", marker: undefined, githubUserId: 7 })] });
    expect(items[0].marker).toBe("Opora-Identity: id_1 abc123");
    const shown = publicIdentities(items);
    expect(shown.every(item => !("marker" in item))).toBe(true);
    expect(JSON.stringify(shown)).not.toContain("abc123");
  });
  it("rejects unknown states", () => {
    expect(() => parseIdentities({ items: [row({ state: "maybe" })] })).toThrow();
  });
  it("links only https github evidence", () => {
    expect(evidenceUrl({ evidence: { url: "https://github.com/o/r/pull/1#issuecomment-2" } })).toContain("github.com");
    expect(evidenceUrl({ evidence: { url: "javascript:alert(1)" } })).toBeNull();
  });
  it("maps error codes to Czech", () => {
    expect(identityError({ status: 409, body: { code: "identity_proof_missing" } })).toContain("Komentář");
    expect(identityError({ status: 428, body: {} })).toContain("identita");
  });
});
