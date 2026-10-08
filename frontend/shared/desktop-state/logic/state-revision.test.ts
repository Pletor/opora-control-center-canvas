import { expect, it } from "vitest";
import { retainSnapshot } from "./state-revision";
import { emptyDesktopState, type StateResponse } from "./types";
it("keeps state identity for unchanged scoped revision, not for another scope", () => {
  const first: StateResponse = {revision:1,state:emptyDesktopState(),readOnly:false};
  const previous = {scope:"p:w",value:first};
  expect(retainSnapshot(previous,"p:w",structuredClone(first))).toBe(first);
  expect(retainSnapshot(previous,"q:w",structuredClone(first))).not.toBe(first);
  const changed={...first,revision:2};
  expect(retainSnapshot(previous,"p:w",changed)).toBe(changed);
});
