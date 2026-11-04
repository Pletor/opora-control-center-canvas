import { expect, it } from "vitest";
import type { FlowVersion, VersionStatus } from "@/shared/flow-editor/logic/flow-types";
import { history, pickFlowVersion, versionAction } from "./library-versions";

const v = (n: number, status: VersionStatus): FlowVersion => ({ id: `v${n}`, workflow_id: "w", n, graph: { nodes: [], edges: [] }, hash: "", parent_version_id: null, status, eval_run_id: null, created_at: "" });

it("shows the newer draft first, then the active version, and offers the matching action", () => {
  const versions = [v(1, "retired"), v(2, "active"), v(3, "draft")];
  expect(pickFlowVersion(versions, null)?.id).toBe("v3");
  expect(pickFlowVersion(versions, "v1")?.id).toBe("v1");
  expect(pickFlowVersion([v(1, "draft"), v(2, "active")], null)?.id).toBe("v2");
  expect(pickFlowVersion([], null)).toBeNull();
  expect(versionAction(versions, versions[2])).toBe("activate");
  expect(versionAction(versions, versions[0])).toBe("restore");
  expect(versionAction(versions, versions[1])).toBe("rollback");
  expect(versionAction([v(1, "active")], v(1, "active"))).toBeNull();
  expect(history(versions).map((item) => item.n)).toEqual([3, 2, 1]);
});
