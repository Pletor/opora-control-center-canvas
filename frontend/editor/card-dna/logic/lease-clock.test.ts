import { describe, expect, it } from "vitest";
import { createLeaseClock } from "./lease-clock";

describe("createLeaseClock", () => {
  it("shares exactly one interval across subscribers and stops after the last unsubscribe", () => {
    let started = 0;
    let stopped = 0;
    let tick: (() => void) | undefined;
    const clock = createLeaseClock({
      now: () => 10_000,
      setInterval: (callback) => { started += 1; tick = callback; return 7 as unknown as ReturnType<typeof setInterval>; },
      clearInterval: () => { stopped += 1; },
    });
    const moments: number[] = [];
    const first = clock.subscribe(() => moments.push(clock.getSnapshot()));
    const second = clock.subscribe(() => moments.push(clock.getSnapshot()));
    expect(started).toBe(1);
    tick?.();
    expect(moments).toEqual([10_000, 10_000]);
    first();
    expect(stopped).toBe(0);
    second();
    expect(stopped).toBe(1);
  });
});
