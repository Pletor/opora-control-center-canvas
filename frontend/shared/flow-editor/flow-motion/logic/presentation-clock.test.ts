// Převedeno z prototypu `prototype/test/presentation-clock.test.mjs` (node:test → vitest), plus návrat po pauze.
import { describe, expect, it } from "vitest";
import { PresentationClock } from "./presentation-clock";

describe("PresentationClock", () => {
  it("paused ticks move phase immediately, repeated render and time do not replay it", () => {
    const c = new PresentationClock(); c.setFrame({ tick: 0 }, 0); c.setFrame({ tick: 1 }, 10);
    expect(c.time).toBe(280); c.advance(2400); c.setFrame({ tick: 1 }, 2500); expect(c.time).toBe(280);
    c.setFrame({ tick: 4 }, 2600); expect(c.time).toBe(1120); expect(c.sweepTime).toBe(0);
  });

  it("running clock uses elapsed wall time, independent of model tick cadence", () => {
    const c = new PresentationClock(); c.setFrame({ running: true, tick: 1 }, 0); c.advance(500);
    expect(c.time).toBe(500); c.setFrame({ running: true, tick: 3 }, 500); c.advance(1000);
    expect(c.time).toBe(1000); expect(c.sweepTime).toBe(1000);
    c.setFrame({ running: false, tick: 3 }, 1100); expect(c.time).toBe(1100); expect(c.sweepTime).toBe(0);
    c.advance(9000); expect(c.time).toBe(1100);
    c.setFrame({ running: true, tick: 3 }, 9000); c.advance(9200); expect(c.time).toBe(1300); expect(c.sweepTime).toBe(200);
  });

  it("reset, domain switch and suspended presentation never inherit elapsed time", () => {
    const c = new PresentationClock(); c.setFrame({ running: true, tick: 4, key: "a" }, 0); c.advance(1000);
    c.advance(2000, true); expect(c.time).toBe(1000); c.advance(2200); expect(c.time).toBe(1200);
    c.setFrame({ tick: 0, key: "a" }, 2300); expect(c.time).toBe(0);
    c.setFrame({ tick: 1, key: "a" }, 2400); expect(c.time).toBe(280);
    c.setFrame({ tick: 0, key: "b" }, 2500); expect(c.time).toBe(0);
  });

  it("resync after a hidden document skips the time nobody saw", () => {
    const c = new PresentationClock(); c.setFrame({ running: true, key: "level" }, 0); c.advance(400);
    c.resync(60_000); c.advance(60_100); expect(c.time).toBe(500);
  });
});
