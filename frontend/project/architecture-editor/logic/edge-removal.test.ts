import { describe, expect, it } from "vitest";
import type { RemovalPreview } from "@/shared/types/logic/types";
import { edgeRemovalPreviewUrl, edgeRemovalRequest } from "./edge-removal";

const scope = { project: "p1", workspace: "wt-a" };
const preview = (patch: Partial<RemovalPreview> = {}): RemovalPreview => ({
  project: "p1", workspace: "wt-a", kind: "edge", target: "e1", label: "A → B", nodeIds: [], nodeCount: 0, edgeCount: 1, digest: "abc", ...patch,
});

describe("odstranění vazby přes náhled", () => {
  it("náhled se ptá na vazbu v otevřeném prostoru", () => {
    const url = edgeRemovalPreviewUrl(scope, "e 1");
    expect(url.startsWith("/api/removal-preview?")).toBe(true);
    expect(Object.fromEntries(new URLSearchParams(url.split("?")[1]))).toEqual({ project: "p1", workspace: "wt-a", kind: "edge", target: "e 1" });
  });
  it("odstranění nese otisk náhledu a výslovné potvrzení, nic navíc", () => {
    expect(edgeRemovalRequest(scope, "e1", preview())).toEqual({ project: "p1", workspace: "wt-a", kind: "edge", target: "e1", digest: "abc", confirmed: true });
  });
  it("náhled jiné vazby, druhu nebo prostoru odmítne", () => {
    expect(() => edgeRemovalRequest(scope, "e1", preview({ target: "e2" }))).toThrow("nepatří");
    expect(() => edgeRemovalRequest(scope, "e1", preview({ kind: "node" }))).toThrow("nepatří");
    expect(() => edgeRemovalRequest(scope, "e1", preview({ workspace: "main" }))).toThrow("nepatří");
  });
});
