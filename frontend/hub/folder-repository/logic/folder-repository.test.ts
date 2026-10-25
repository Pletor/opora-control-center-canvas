import { describe, expect, it } from "vitest";
import { bindPayload, parseStatus } from "./folder-repository";

const status = (over: Record<string, unknown> = {}) => ({ project: "p1", applies: true, bindable: true, binding: null,
  detectedRepository: "pletor/ample", canConfigure: true, unavailableReason: null, ...over });

describe("folder repository binding", () => {
  it("parses the server status and a stored binding", () => {
    expect(parseStatus(status()).detectedRepository).toBe("pletor/ample");
    const bound = parseStatus(status({ binding: { repository: "pletor/ample", branch: "main", boundAt: "2026-10-25T10:00:00Z" } }));
    expect(bound.binding?.branch).toBe("main");
  });
  it("rejects a malformed status", () => {
    expect(() => parseStatus(status({ applies: "yes" }))).toThrow();
    expect(() => parseStatus(status({ binding: { repository: 1 } }))).toThrow();
  });
  it("builds a payload only from a valid owner/repo and branch", () => {
    expect(bindPayload("p1", " pletor/ample ", "main")).toEqual({ project: "p1", repository: "pletor/ample", branch: "main" });
    expect(bindPayload("p1", "https://github.com/pletor/ample", "main")).toBeNull();
    expect(bindPayload("p1", "pletor/ample", "-x")).toBeNull();
    expect(bindPayload("p1", "pletor/../ample", "main")).toBeNull();
  });
});
