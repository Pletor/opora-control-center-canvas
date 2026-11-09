import { expect, it, vi } from "vitest";
import { runScopedReview, selectedDesktopReview } from "./DesktopReview";
it("never substitutes a review from another scope or malformed identifier", () => {
  expect(selectedDesktopReview("?project=p&workspace=w&desktopReview=review-1", "p", "w")).toBe("review-1");
  expect(selectedDesktopReview("?project=p&workspace=other&desktopReview=review-1", "p", "w")).toBeNull();
  expect(selectedDesktopReview("?project=other&workspace=w&desktopReview=review-1", "p", "w")).toBeNull();
  expect(selectedDesktopReview("?project=p&workspace=w&desktopReview=../wrong", "p", "w")).toBeNull();
});
it.each([false, true])("does not publish an old in-flight review result after scope change (failure=%s)", async failure => {
  const oldScope = { project: "p", workspace: "w", review: "a" };
  let current = oldScope;
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const pending = new Promise<void>((done, fail) => { resolve = done; reject = fail; });
  const success = vi.fn(), error = vi.fn(), finish = vi.fn();
  const run = runScopedReview(() => pending, () => current === oldScope, success, error, finish);
  current = { project: "p", workspace: "new", review: "b" };
  if (failure) reject(new Error("Old action failed")); else resolve();
  await run;
  expect(success).not.toHaveBeenCalled(); expect(error).not.toHaveBeenCalled(); expect(finish).not.toHaveBeenCalled();
});
it("publishes the current scope result and releases its busy state", async () => {
  const success = vi.fn(), failure = vi.fn(), finish = vi.fn();
  await runScopedReview(async () => undefined, () => true, success, failure, finish);
  expect(success).toHaveBeenCalledOnce(); expect(finish).toHaveBeenCalledOnce(); expect(failure).not.toHaveBeenCalled();
});
