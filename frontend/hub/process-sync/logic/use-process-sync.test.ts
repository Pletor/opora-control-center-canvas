import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readProcess, watchProcess, type ProcessEnvironment, type ProcessState } from "./process-reader";
import { processFixture } from "./process-fixtures";
import type { ProcessSnapshot } from "./process-sync";

function fixture(project = "draft") {
  let visible = true;
  const events = new Map<string, () => void>(), commits: ProcessState[] = [];
  const pending: { signal: AbortSignal; resolve: (snapshot: ProcessSnapshot) => void; reject: (error: Error) => void }[] = [];
  const cleanups = vi.fn();
  const environment: ProcessEnvironment = { visible: () => visible, listen: (event, callback) => {
    events.set(event, callback); return () => { cleanups(); events.delete(event); };
  } };
  const read = vi.fn((_project: string, _workspace: string, signal: AbortSignal) => new Promise<ProcessSnapshot>((resolve, reject) => {
    pending.push({ signal, resolve, reject });
  }));
  const watcher = watchProcess(project, "draft", state => commits.push(state), environment, read);
  return { watcher, commits, pending, read, events, cleanups, visible: (value: boolean) => { visible = value; } };
}
const settle = async () => { await vi.advanceTimersByTimeAsync(0); };
beforeEach(() => vi.useFakeTimers());
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("useProcessSync scoped read lifetime", () => {
  it("refresh supersedes without aborting, so the server never computes two reads at once", async () => {
    const f = fixture();
    // An aborted fetch would free the poller while the server still computes the read under the project lock.
    f.watcher.refresh(); expect(f.pending[0].signal.aborted).toBe(false);
    expect(f.read).toHaveBeenCalledTimes(1); // Canonical poller never overlaps requests.
    f.pending[0].resolve(processFixture("obsolete")); await settle();
    f.pending[1].resolve(processFixture()); await settle();
    const count = f.commits.length;
    f.pending[0].resolve(processFixture("obsolete")); await settle();
    expect(f.commits.length).toBe(count); expect(f.commits.at(-1)?.snapshot?.project).toBe("draft");
    f.watcher.refresh(); f.watcher.refresh();
    f.pending[2].reject(new Error("old error")); await settle();
    expect(f.commits.at(-1)?.error).toBe(""); f.watcher.close();
  });
  it("scope change/unmount closes old work and listener/timer callbacks cannot publish", async () => {
    const first = fixture("first"); const oldFocus = first.events.get("focus")!;
    first.watcher.close(); const next = fixture("second");
    expect(first.pending[0].signal.aborted).toBe(true); expect(first.cleanups).toHaveBeenCalledTimes(2);
    const count = first.commits.length; oldFocus(); first.pending[0].resolve(processFixture("first")); await settle();
    expect(first.commits.length).toBe(count); expect(first.read).toHaveBeenCalledTimes(1);
    next.pending[0].resolve(processFixture("second")); await settle();
    expect(next.commits.at(-1)?.snapshot?.project).toBe("second"); next.watcher.close();
  });
  it("polls/focuses only while visible and supersedes in-flight work when hidden", async () => {
    const f = fixture(); f.visible(false); f.events.get("visibilitychange")!();
    expect(f.pending[0].signal.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(60000); f.events.get("focus")!(); expect(f.read).toHaveBeenCalledTimes(1);
    f.pending[0].resolve(processFixture()); await settle(); expect(f.commits.at(-1)?.snapshot).toBeNull();
    f.visible(true); f.events.get("visibilitychange")!(); expect(f.read).toHaveBeenCalledTimes(2);
    f.events.get("focus")!(); expect(f.read).toHaveBeenCalledTimes(2);
    f.pending[1].resolve(processFixture()); await settle();
    await vi.advanceTimersByTimeAsync(14999); expect(f.read).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1); expect(f.read).toHaveBeenCalledTimes(3); f.watcher.close();
  });
  it("retains the same scoped snapshot for stable opener DOM while marking refresh or error", async () => {
    const f = fixture(), snapshot = processFixture(); f.pending[0].resolve(snapshot); await settle();
    expect(f.commits.at(-1)?.snapshot).not.toBeNull(); f.watcher.refresh();
    expect(f.commits.at(-1)).toEqual({ snapshot, busy: true, error: "" });
    expect(f.commits.at(-1)?.snapshot).toBe(snapshot);
    f.pending[1].reject(new Error("unavailable")); await settle();
    expect(f.commits.at(-1)?.snapshot).toBe(snapshot); expect(f.commits.at(-1)?.error).not.toBe(""); f.watcher.close();
  });
  it("returning before a superseded read settles queues one fresh read without overlapping", async () => {
    const f = fixture(); f.visible(false); f.events.get("visibilitychange")!();
    f.visible(true); f.events.get("visibilitychange")!(); f.events.get("focus")!();
    expect(f.read).toHaveBeenCalledTimes(1);
    f.pending[0].resolve(processFixture("obsolete")); await settle();
    expect(f.read).toHaveBeenCalledTimes(2); expect(f.commits.at(-1)?.snapshot).toBeNull();
    f.pending[1].resolve(processFixture()); await settle();
    expect(f.commits.at(-1)?.snapshot?.project).toBe("draft"); f.watcher.close();
  });
  it("actual reader passes abort/no-store and rejects failed HTTP or replies from another scope", async () => {
    const controller = new AbortController(), transport = vi.fn(); vi.stubGlobal("fetch", transport);
    transport.mockResolvedValueOnce(Response.json(processFixture()));
    expect((await readProcess("draft", "draft", controller.signal)).project).toBe("draft");
    expect(transport).toHaveBeenLastCalledWith("/api/oporahub/process?project=draft&workspace=draft",
      { signal: controller.signal, cache: "no-store", redirect: "error" });
    transport.mockResolvedValueOnce(Response.json({ error: "private details" }, { status: 500 }));
    await expect(readProcess("draft", "draft", controller.signal)).rejects.toThrow("HTTP 500");
    transport.mockResolvedValueOnce(Response.json(processFixture("other")));
    await expect(readProcess("draft", "draft", controller.signal)).rejects.toThrow("jiný pracovní prostor");
  });
  it("authentication failure requests the existing access gate and never treats an error body as process data", async () => {
    const dispatchEvent = vi.fn(); vi.stubGlobal("window", { dispatchEvent });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ error: "Unauthorized" }, { status: 401 })));
    await expect(readProcess("draft", "draft", new AbortController().signal)).rejects.toThrow("HTTP 401");
    expect(dispatchEvent).toHaveBeenCalledOnce(); expect(dispatchEvent.mock.calls[0][0]).toBeInstanceOf(Event);
  });
});
