import { describe, expect, it } from "vitest";
import { consentText, jevState, type JevStatus } from "./jev-check";

const status = (configured: boolean, provider: JevStatus["provider"] = "celeris"): JevStatus =>
  ({ configured, provider, keys: { typesafe: false, celeris: configured } });

describe("jev gate check permission", () => {
  it("reads the state for the active provider: key, then human permission for the project", () => {
    expect(jevState(undefined, undefined)).toBe("unknown");
    expect(jevState(status(false), { project: "p", allowed: { typesafe: false, celeris: true } })).toBe("not-configured");
    expect(jevState(status(true), { project: "p", allowed: { typesafe: true, celeris: false } })).toBe("not-allowed");
    expect(jevState(status(true), { project: "p", allowed: { typesafe: false, celeris: true } })).toBe("allowed");
  });

  it("says plainly what leaves the computer", () => {
    expect(consentText("celeris")).toContain("Celeris");
    expect(consentText("typesafe")).toMatch(/název fragmentu, jeho text \(nejvýš 4000 znaků\), název brány a payload/);
  });
});
