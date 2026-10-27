import { describe, expect, it } from "vitest";
import type { MotionEnv } from "../../studio-motion/logic/particle-animator";
import { FlowAnimator } from "./flow-animator";
import type { FlowParticle } from "./model-particles";

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
const path = { getTotalLength: () => 100, getPointAtLength: (distance: number) => ({ x: distance, y: 0 }) };
const dot = () => { const attrs: Record<string, string> = {}; return { attrs, setAttribute: (name: string, value: string) => { attrs[name] = value; } }; };
const particle: FlowParticle = { kind: "accepted", ordinal: 0, count: 1, duration: 1000, roundTrip: false, dwell: .1, amount: 10, color: "#fff" };

describe("flow animator", () => {
  it("moves particles only while the run is running", () => {
    const { env, flush, setNow, pending } = fakeEnv();
    const animator = new FlowAnimator(env); animator.attach();
    const d = dot();
    animator.add(d, path, particle);
    expect(d.attrs.cx).toBe("0.00");
    expect(pending()).toBe(0);
    setNow(0); animator.setFrame({ running: true, tick: 1, key: "m" });
    expect(pending()).toBe(1);
    flush(250); expect(d.attrs.cx).toBe("25.00");
    setNow(300); animator.setFrame({ running: false, tick: 1, key: "m" });
    flush(900); expect(animator.looping).toBe(false);
    expect(d.attrs.cx).toBe("30.00");
  });

  it("shifts a paused step by 280 ms and restarts on a new context", () => {
    const { env } = fakeEnv();
    const animator = new FlowAnimator(env);
    const d = dot();
    animator.add(d, path, particle);
    animator.setFrame({ running: false, tick: 1, key: "m" });
    expect(d.attrs.cx).toBe("28.00");
    animator.setFrame({ running: false, tick: 2, key: "m" });
    expect(d.attrs.cx).toBe("56.00");
    animator.setFrame({ running: false, tick: 0, key: "other" });
    expect(animator.clock.time).toBe(0);
  });

  it("stops the loop when the document is hidden or motion is reduced, and forgets removed dots", () => {
    const { env, state, flush, pending } = fakeEnv();
    const animator = new FlowAnimator(env); animator.attach();
    const remove = animator.add(dot(), path, particle);
    animator.setFrame({ running: true, tick: 1, key: "m" });
    state.reduced = true; flush(100);
    expect(pending()).toBe(0);
    state.reduced = false; state.change();
    expect(pending()).toBe(1);
    remove(); flush(200);
    expect(animator.size).toBe(0);
    expect(pending()).toBe(0);
    animator.detach();
  });
});
