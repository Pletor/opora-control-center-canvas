import { describe, expect, it } from "vitest";
import { STILL, markerMotion } from "./marker-motion";

const last = (key: string, kind = "x", state = "progress") => ({ key, kind, state });

describe("marker moves only on a real event", () => {
  it("stays still on first render and when no new event came", () => {
    expect(markerMotion(undefined, 2, last("a"))).toEqual(STILL);
    expect(markerMotion({ phase: 1, lastKey: "a" }, 2, last("a"))).toEqual(STILL);
  });
  it("slides from the old cell on phase change, pulses on tool.use, shakes on fail", () => {
    expect(markerMotion({ phase: 1, lastKey: "a" }, 3, last("b"))).toEqual({ shift: -2, pulse: false, shake: false });
    expect(markerMotion({ phase: 2, lastKey: "a" }, 2, last("b", "tool.use"))).toEqual({ shift: 0, pulse: true, shake: false });
    expect(markerMotion({ phase: 3, lastKey: "a" }, 3, last("b", "pr.checks", "fail"))).toEqual({ shift: 0, pulse: false, shake: true });
  });
});
