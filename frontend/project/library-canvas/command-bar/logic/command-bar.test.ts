import { describe, expect, it } from "vitest";
import type { FlowVersion } from "@/shared/flow-editor/logic/flow-types";
import { commandNodeIds, flowContext, heartWrote, opensCommandBar, snapshotOf } from "./command-bar";

const key = (key: string, extra: Partial<{ ctrlKey: boolean; metaKey: boolean; altKey: boolean; target: { tagName: string } | null }> = {}) =>
  ({ key, ctrlKey: false, metaKey: false, altKey: false, target: { tagName: "DIV" }, ...extra });
const version = (id: string, n: number, status: FlowVersion["status"], hash: string) =>
  ({ id, workflow_id: "w", n, graph: { nodes: [], edges: [] }, hash, parent_version_id: null, status, eval_run_id: null, created_at: "" }) as FlowVersion;

describe("command bar", () => {
  it("opens with / or Ctrl+K unless the focus is in a field", () => {
    expect(opensCommandBar(key("/"))).toBe(true);
    expect(opensCommandBar(key("k", { ctrlKey: true }))).toBe(true);
    expect(opensCommandBar(key("K", { metaKey: true }))).toBe(true);
    expect(opensCommandBar(key("/", { target: { tagName: "INPUT" } }))).toBe(false);
    expect(opensCommandBar(key("k", { ctrlKey: true, target: { tagName: "TEXTAREA" } }))).toBe(false);
    expect(opensCommandBar(key("a"))).toBe(false);
    expect(opensCommandBar(key("/", { ctrlKey: true }))).toBe(false);
  });
  it("merges the clicked node with the framed ones, without duplicates or vanished nodes", () => {
    expect(commandNodeIds("b", ["a", "b", "c"], ["a", "b", "c"])).toEqual(["b", "a", "c"]);
    expect(commandNodeIds(null, ["a", "gone"], ["a", "b"])).toEqual(["a"]);
    expect(commandNodeIds(null, [], ["a"])).toEqual([]);
  });
  it("sends the flow, the viewed version and only the selected nodes", () => {
    expect(flowContext("f", "v1", ["a"])).toEqual({ kind: "flow", flowId: "f", versionId: "v1", nodeIds: ["a"] });
    expect(flowContext("f", null, [])).toEqual({ kind: "flow", flowId: "f" });
  });
  it("sees a draft that is new or changed since the message was sent", () => {
    const before = [version("a", 1, "active", "h1")], known = snapshotOf(before);
    expect(heartWrote(known, before)).toBeNull();
    expect(heartWrote(known, [...before, version("b", 2, "draft", "h2")])?.id).toBe("b");
    const drafted = [...before, version("b", 2, "draft", "h2")];
    expect(heartWrote(snapshotOf(drafted), drafted)).toBeNull();
    expect(heartWrote(snapshotOf(drafted), [...before, version("b", 2, "draft", "h3")])?.id).toBe("b");
    expect(heartWrote(known, [version("a", 1, "active", "h9")])).toBeNull();
  });
});
