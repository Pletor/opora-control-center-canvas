import { describe, expect, it } from "vitest";
import { ParticleAnimator, type MotionEnv } from "./particle-animator";

/** Ruční prostředí: snímky se spouštějí voláním `flush(čas)`, viditelnost a preference se přepínají. */
function fakeEnv() {
  let now = 0; let next = 1; const frames = new Map<number, (time: number) => void>();
  const state = { hidden: false, reduced: false, change: () => {} };
  const env: MotionEnv = {
    now: () => now,
    frame: (callback) => { frames.set(next, callback); return next++; },
    cancel: (id) => { frames.delete(id); },
    hidden: () => state.hidden, reduced: () => state.reduced,
    watch: (onChange) => { state.change = onChange; return () => { state.change = () => {}; }; },
  };
  const flush = (time: number) => { now = time; const pending = [...frames.values()]; frames.clear(); pending.forEach((callback) => callback(time)); };
  return { env, state, flush, setNow: (time: number) => { now = time; }, pending: () => frames.size };
}
const straightPath = { getTotalLength: () => 100, getPointAtLength: (distance: number) => ({ x: distance, y: 0 }) };
const dot = () => { const attrs: Record<string, string> = {}; return { attrs, setAttribute: (name: string, value: string) => { attrs[name] = value; } }; };

describe("particle animator", () => {
  it("writes looping dots straight into SVG attributes from one frame loop", () => {
    const { env, flush, pending } = fakeEnv();
    const animator = new ParticleAnimator(env); animator.attach();
    const first = dot(); const second = dot();
    animator.add({ dot: first, path: straightPath, mode: "loop", cycle: 1000, index: 0, dots: 2 });
    animator.add({ dot: second, path: straightPath, mode: "loop", cycle: 1000, index: 1, dots: 2 });
    expect(pending()).toBe(1);
    expect(second.attrs).toMatchObject({ cx: "50.00", visibility: "visible" });
    flush(250);
    expect(first.attrs.cx).toBe("25.00"); expect(second.attrs.cx).toBe("75.00");
  });

  it("runs a one-shot dot once and hides it before and after", () => {
    const { env, flush } = fakeEnv();
    const animator = new ParticleAnimator(env);
    const once = dot();
    const remove = animator.add({ dot: once, path: straightPath, mode: "once", delay: 100, duration: 1000 });
    expect(once.attrs.visibility).toBe("hidden");
    flush(600); expect(once.attrs).toMatchObject({ cx: "50.00", visibility: "visible" });
    flush(1200); expect(once.attrs.visibility).toBe("hidden");
    remove(); expect(animator.size).toBe(0);
    flush(1300); expect(animator.looping).toBe(false);
  });

  it("stops while the document is hidden and resumes without catching up", () => {
    const { env, state, flush, setNow } = fakeEnv();
    const animator = new ParticleAnimator(env); animator.attach();
    const moving = dot();
    animator.add({ dot: moving, path: straightPath, mode: "loop", cycle: 1000, index: 0, dots: 1 });
    flush(200); expect(moving.attrs.cx).toBe("20.00");
    state.hidden = true; flush(300);
    expect(animator.looping).toBe(false); expect(moving.attrs.cx).toBe("20.00");
    setNow(50_000); state.hidden = false; state.change();
    expect(animator.looping).toBe(true);
    flush(50_100); expect(moving.attrs.cx).toBe("30.00");
  });

  it("does not loop at all with reduced motion", () => {
    const { env, state } = fakeEnv(); state.reduced = true;
    const animator = new ParticleAnimator(env);
    animator.add({ dot: dot(), path: straightPath, mode: "loop", cycle: 1000, index: 0, dots: 2 });
    expect(animator.looping).toBe(false);
  });
});
