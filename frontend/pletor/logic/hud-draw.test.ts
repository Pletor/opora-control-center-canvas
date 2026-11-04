import { describe, expect, it, vi } from "vitest";
import { drawHud, stepHud, type HudFrame } from "./hud-draw";
import { HUD_GREEN, HUD_THINKING } from "./hud-palette";

/** Kontext plátna jako záznamník: každá metoda je vi.fn, gradient umí addColorStop, vlastnosti se jen ukládají. */
function mockCtx(conic: boolean) {
  const calls: Record<string, ReturnType<typeof vi.fn>> = {};
  const gradient = { addColorStop: vi.fn() };
  const fn = (name: string) => (calls[name] ??= vi.fn(() => (name.startsWith("create") ? gradient : undefined)));
  const ctx = new Proxy({} as Record<string, unknown>, {
    get: (store, key: string) => (key in store ? store[key] : key === "createConicGradient" && !conic ? undefined : fn(key)),
    set: (store, key: string, value) => { store[key] = value; return true; },
  });
  return { ctx: ctx as unknown as CanvasRenderingContext2D, calls };
}

const frame = (): HudFrame => ({ w: 600, h: 400, t: 1.5, rot: 0.3, amp: 0.2, font: "monospace" });

describe("drawHud", () => {
  it("vykreslí prstence obloukem a nehodí", () => {
    const { ctx, calls } = mockCtx(true);
    expect(() => drawHud(ctx, frame(), HUD_GREEN, "idle")).not.toThrow();
    expect(calls.arc.mock.calls.length).toBeGreaterThan(40);
    expect(calls.fillText).toHaveBeenCalledTimes(12);
    expect(calls.createConicGradient).toBeUndefined();
  });
  it("při přemýšlení zapne skener; bez kuželového gradientu se obejde", () => {
    const withConic = mockCtx(true);
    drawHud(withConic.ctx, frame(), HUD_THINKING, "thinking");
    expect(withConic.calls.createConicGradient).toHaveBeenCalledOnce();
    expect(() => drawHud(mockCtx(false).ctx, frame(), HUD_THINKING, "thinking")).not.toThrow();
  });
  it("nulový rozměr jen smaže plátno", () => {
    const { ctx, calls } = mockCtx(true);
    drawHud(ctx, { ...frame(), w: 0 }, HUD_GREEN, "idle");
    expect(calls.clearRect).toHaveBeenCalledOnce();
    expect(calls.arc).toBeUndefined();
  });
});

describe("stepHud", () => {
  it("přemýšlení točí rychleji než klid, bez pohybu se skoro netočí", () => {
    const idle = frame(), thinking = frame(), still = frame();
    stepHud(idle, 0.05, "idle", false);
    stepHud(thinking, 0.05, "thinking", false);
    stepHud(still, 0.05, "thinking", true);
    expect(thinking.rot - 0.3).toBeGreaterThan(idle.rot - 0.3);
    expect(still.rot - 0.3).toBeLessThan((idle.rot - 0.3) / 10);
  });
  it("odpověď zvedá amplitudu", () => {
    const speaking = frame();
    for (let i = 0; i < 40; i++) stepHud(speaking, 0.05, "speaking", false);
    expect(speaking.amp).toBeGreaterThan(0.6);
  });
});
