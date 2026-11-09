import { afterEach, expect, it, vi } from "vitest";
import { observedStructure, togglePrivateGroup } from "./structure-view";

afterEach(() => vi.unstubAllGlobals());
it("requires all actual visible group controls to match before acknowledgement", () => {
  const expanded = { sectors: "false", nodes: "true", areas: "true" };
  let hidden = false;
  vi.stubGlobal("getComputedStyle", () => ({ visibility: "visible" }));
  const root = { querySelector: (selector: string) => {
    const group = /group-(\w+)/.exec(selector)![1] as keyof typeof expanded;
    return { getClientRects: () => hidden ? [] : [{}], getAttribute: () => expanded[group] };
  } } as unknown as ParentNode;
  expect(observedStructure(["sectors"], root)).toBe(true);
  expect(observedStructure([], root)).toBe(false);
  hidden = true;
  expect(observedStructure(["sectors"], root)).toBe(false);
  expect(observedStructure(undefined, root)).toBe(true);
  expect(observedStructure([], { querySelector: () => null } as unknown as ParentNode)).toBe(false);
});
it("manual private toggles preserve the original preference array", () => {
  const saved = ["areas"] as const;
  const privateGroups = togglePrivateGroup([...saved], "nodes");
  expect(privateGroups).toEqual(["areas", "nodes"]);
  expect(togglePrivateGroup(privateGroups, "areas")).toEqual(["nodes"]);
  expect(saved).toEqual(["areas"]);
});
