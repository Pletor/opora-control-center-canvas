import { describe, expect, it, vi } from "vitest";
import { createDraftGuard } from "./draft-guard";

describe("DNA guard před odmountováním", () => {
  it.each(["Esc", "křížek", "záložka", "skrýt důkazy"])("%s počká na uložení participantů", async () => {
    let dirty = true;
    let release!: () => void;
    const flush = vi.fn(async () => { await new Promise<void>(resolve => { release = resolve; }); dirty = false; });
    const change = vi.fn();
    const guard = createDraftGuard({ entries: () => dirty ? [{ dirty: true, pending: false }] : [], flush, report: vi.fn() });
    const result = guard(change);
    expect(change).not.toHaveBeenCalled();
    release(); await result;
    expect(flush).toHaveBeenCalledOnce(); expect(change).toHaveBeenCalledOnce();
  });
  it("blokovaný editor nebo neúspěšné uložení zůstane namountovaný s rozhodnutím ve formuláři", async () => {
    const change = vi.fn(); const report = vi.fn();
    const guard = createDraftGuard({ entries: () => [{ dirty: true, pending: false }], flush: async () => { throw new Error("Uložte nebo zrušte důkazy."); }, report });
    await guard(change);
    expect(change).not.toHaveBeenCalled(); expect(report).toHaveBeenLastCalledWith("Uložte nebo zrušte důkazy.");
  });
  it("nepovažuje neověřené uložení za úspěch", async () => {
    const change = vi.fn(); const report = vi.fn();
    await createDraftGuard({ entries: () => [{ dirty: true, pending: false }], flush: async () => {}, report })(change);
    expect(change).not.toHaveBeenCalled(); expect(report).toHaveBeenLastCalledWith(expect.stringContaining("Koncept"));
  });
  it("běžící zápis i opakovaný klik nesmějí odmountovat editor před potvrzením", async () => {
    let pending = true; let release!: () => void;
    const change = vi.fn();
    const guard = createDraftGuard({ entries: () => pending ? [{ dirty: false, pending: true }] : [], flush: async () => { await new Promise<void>(resolve => { release = resolve; }); pending = false; }, report: vi.fn() });
    const first = guard(change); await guard(change); expect(change).not.toHaveBeenCalled();
    release(); await first; expect(change).toHaveBeenCalledOnce();
  });
  it("čistý panel přepne bez ukládání", async () => {
    const change = vi.fn(); const flush = vi.fn();
    await createDraftGuard({ entries: () => [], flush, report: vi.fn() })(change);
    expect(change).toHaveBeenCalledOnce(); expect(flush).not.toHaveBeenCalled();
  });
});
