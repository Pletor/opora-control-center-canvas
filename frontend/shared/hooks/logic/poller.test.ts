import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPoller, type VisibilitySource } from "./poller";
import { sameKeys } from "./use-polling";

function visibility() {
  let hidden = false;
  const listeners = new Set<() => void>();
  const source: VisibilitySource = { hidden: () => hidden, subscribe: (l) => { listeners.add(l); return () => listeners.delete(l); } };
  return { source, set(value: boolean) { hidden = value; listeners.forEach((l) => l()); }, listeners };
}

/** Dotaz, který skončí až na pokyn testu: `active` = kolik jich právě běží, `max` = nejvíc najednou. */
function slowRequests() {
  const pending: (() => void)[] = [];
  const stats = { calls: 0, active: 0, max: 0 };
  const run = vi.fn(() => new Promise<void>((resolve) => {
    stats.calls += 1; stats.active += 1; stats.max = Math.max(stats.max, stats.active);
    pending.push(() => { stats.active -= 1; resolve(); });
  }));
  return { run, stats, finishAll: async () => { while (pending.length) pending.shift()!(); await vi.advanceTimersByTimeAsync(0); } };
}

describe("sdílený poller", () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("nespustí nový dotaz, dokud běží předchozí, ani když interval mezitím uplyne", async () => {
    const { run, stats, finishAll } = slowRequests();
    const poller = createPoller({ run, intervalMs: 3000, visibility: visibility().source });
    poller.start();
    await vi.advanceTimersByTimeAsync(20_000);
    expect(stats).toMatchObject({ calls: 1, max: 1 });
    await finishAll();
    await vi.advanceTimersByTimeAsync(3000);
    expect(stats).toMatchObject({ calls: 2, max: 1 });
    poller.stop();
  });

  it("refresh během běhu se slije do jednoho dotazu hned po něm; poke nic nepřidá", async () => {
    const { run, stats, finishAll } = slowRequests();
    const poller = createPoller({ run, intervalMs: 30_000, visibility: visibility().source });
    poller.start();
    void poller.refresh(); void poller.refresh(); void poller.poke();
    expect(stats).toMatchObject({ calls: 1, active: 1 });
    await finishAll();
    expect(stats).toMatchObject({ calls: 2, max: 1 });
    void poller.poke();
    expect(stats.calls).toBe(2);
    await finishAll();
    poller.stop();
  });

  it("ve skryté záložce nepolluje a po návratu načte právě jednou", async () => {
    const page = visibility();
    const run = vi.fn(async () => {});
    const poller = createPoller({ run, intervalMs: 5000, visibility: page.source });
    poller.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(run).toHaveBeenCalledTimes(1);
    page.set(true);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(run).toHaveBeenCalledTimes(1);
    page.set(false);
    await vi.advanceTimersByTimeAsync(0);
    expect(run).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(5000);
    expect(run).toHaveBeenCalledTimes(3);
    poller.stop();
    expect(page.listeners.size).toBe(0);
  });

  it("skrytá záložka při startu nenačítá; návrat bez zmeškaného kola nic nepřidá", async () => {
    const page = visibility();
    page.set(true);
    const run = vi.fn(async () => {});
    const poller = createPoller({ run, intervalMs: 5000, visibility: page.source });
    poller.start();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(run).not.toHaveBeenCalled();
    page.set(false);
    await vi.advanceTimersByTimeAsync(0);
    expect(run).toHaveBeenCalledTimes(1);
    page.set(false);
    await vi.advanceTimersByTimeAsync(0);
    expect(run).toHaveBeenCalledTimes(1);
    poller.stop();
  });

  it("immediate=false čeká na první interval; stop zastaví další kola; chyba poller nezastaví", async () => {
    const run = vi.fn(async () => { throw new Error("síť"); });
    const poller = createPoller({ run, intervalMs: 30_000, immediate: false, visibility: visibility().source });
    poller.start();
    await vi.advanceTimersByTimeAsync(29_999);
    expect(run).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(30_001);
    expect(run).toHaveBeenCalledTimes(2);
    poller.stop();
    await vi.advanceTimersByTimeAsync(120_000);
    expect(run).toHaveBeenCalledTimes(2);
  });

  it("interval jako funkce se čte před každým kolem (odstup po chybě bez nového polleru)", async () => {
    let pause = 10_000;
    const run = vi.fn(async () => {});
    const poller = createPoller({ run, intervalMs: () => pause, visibility: visibility().source });
    poller.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(run).toHaveBeenCalledTimes(1);
    pause = 20_000;
    await vi.advanceTimersByTimeAsync(10_000);
    expect(run).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(19_999);
    expect(run).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(run).toHaveBeenCalledTimes(3);
    pause = 0;
    await vi.advanceTimersByTimeAsync(20_000);
    expect(run).toHaveBeenCalledTimes(4);
    await vi.advanceTimersByTimeAsync(120_000);
    expect(run).toHaveBeenCalledTimes(4);
    poller.stop();
  });

  it("klíče obnovy porovnává jako závislosti efektu", () => {
    const revision = { a: 1 };
    expect(sameKeys(["p", revision], ["p", revision])).toBe(true);
    expect(sameKeys(["p", revision], ["p", { a: 1 }])).toBe(false);
    expect(sameKeys(["p"], ["p", 1])).toBe(false);
  });
});

// Každé periodické čtení UI jde přes sdílený poller (karta P1): `setInterval` smí jen tikat hodinami
// (stav `now` / `clock`), sítě se nedotkne; řetěz `setTimeout(refresh, …)` mimo poller nesmí existovat.
const FRONTEND = fileURLToPath(new URL("../../..", import.meta.url));
const CLOCK = /setInterval\(\s*\(\)\s*=>\s*set(Now|Clock)\(/;

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

describe("žádný poller mimo vzor", () => {
  const files = sources(FRONTEND).map((path) => ({ path: relative(FRONTEND, path).replaceAll("\\", "/"), text: readFileSync(path, "utf-8") }));

  it("setInterval jen pro hodiny", () => {
    const offenders = files.flatMap(({ path, text }) => text.split("\n")
      .filter((line) => line.includes("setInterval(") && !CLOCK.test(line))
      .map((line) => `${path}: ${line.trim()}`));
    expect(offenders).toEqual([]);
  });

  it("žádný ručně řetězený setTimeout polling", () => {
    const offenders = files.filter(({ text }) => /setTimeout\(\s*(refresh|load|poll|check)\s*,/.test(text)).map(({ path }) => path);
    expect(offenders).toEqual([]);
  });

  it("pollery z karty P1 používají sdílený vzor", () => {
    const pollers = [
      "app/components/App.tsx",
      "editor/canvas/save-versions/logic/use-canvas-versions.ts",
      "editor/canvas/node-card/logic/use-leases.ts",
      "editor/canvas/node-card/logic/use-frontier.ts",
      "editor/canvas/node-card/logic/use-work-overview.ts",
      "editor/canvas/node-card/logic/use-source-status.ts",
      "editor/canvas/card-checklist/logic/card-checklist.ts",
      "project/maps/components/MapUpdateMenu.tsx",
      "layout/heart-channel/logic/use-heart-channel.ts",
      "editor/office/components/OfficeWorkspace.tsx",
      "project/architecture-editor/logic/use-domain-live.ts",
    ];
    for (const path of pollers) expect(files.find((file) => file.path === path)?.text, path).toMatch(/usePolling\(/);
    expect(files.find((file) => file.path === "editor/node-detail/brief-vault/logic/brief-vault-store.ts")?.text).toMatch(/createPoller\(/);
  });

  it("výpis verzí plátna se obnovuje po 30 s", () => {
    const text = files.find((file) => file.path === "editor/canvas/save-versions/logic/use-canvas-versions.ts")!.text;
    expect(text).toMatch(/VERSIONS_POLL_MS = 30_000/);
    expect(text).toMatch(/intervalMs: VERSIONS_POLL_MS/);
  });
});
