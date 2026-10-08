import { describe, expect, it } from "vitest";
import { saveScopeEntries, trackSaveWrite, waitForSaveWrites } from "./save-coordinator";

describe("pending save coordination", () => {
  it("waits for API completion and isolates projects", async () => {
    let finish!: () => void;
    const write = trackSaveWrite("a", "draft", new Promise<void>((resolve) => { finish = resolve; }));
    expect(saveScopeEntries("a", "draft").some((entry) => entry.pending)).toBe(true);
    expect(saveScopeEntries("b", "draft")).toEqual([]);
    let waited = false;
    const waiting = waitForSaveWrites("a", "draft").then(() => { waited = true; });
    await Promise.resolve(); expect(waited).toBe(false);
    finish(); await Promise.all([write, waiting]); expect(waited).toBe(true);
    expect(saveScopeEntries("a", "draft")).toEqual([]);
  });
  it("propagates write failure instead of authorizing a checkpoint", async () => {
    let fail!: (cause: Error) => void;
    const write = trackSaveWrite("failure", "draft", new Promise<void>((_, reject) => { fail = reject; }));
    const waiting = waitForSaveWrites("failure", "draft");
    const checks = [expect(write).rejects.toThrow("conflict"), expect(waiting).rejects.toThrow("conflict")];
    fail(new Error("conflict")); await Promise.all(checks);
    expect(saveScopeEntries("failure", "draft")).toEqual([]);
  });
});
