import { expect, it } from "vitest";
import type { FlowVersion } from "@/shared/flow-editor/logic/flow-types";
import { defaultCompare, versionChips } from "./version-bar";

const version = (id: string, n: number, status: FlowVersion["status"], parent: string | null = null): FlowVersion =>
  ({ id, workflow_id: "w", n, graph: { nodes: [], edges: [] }, hash: "abcdef123456", parent_version_id: parent, status, eval_run_id: null, created_at: "2026-11-03T10:00:00Z" });

it("lists versions newest first with Czech status and compares with the parent by default", () => {
  const versions = [version("a", 1, "active"), version("b", 2, "candidate", "a"), version("c", 3, "draft", "zmizelá")];
  expect(versionChips(versions, "b").map((c) => [c.label, c.statusLabel, c.current])).toEqual([
    ["v3", "draft", false], ["v2", "kandidát", true], ["v1", "aktivní", false]]);
  expect(defaultCompare(versions, versions[1])).toBe("a");
  expect(defaultCompare(versions, versions[2])).toBeNull();
  expect(defaultCompare(versions, null)).toBeNull();
});
