import { describe, expect, it } from "vitest";
import { portColor } from "../../model/logic/catalog";
import { ERROR_COLOR, linkParticles, particleCount, particleDuration, particleProgress, type FlowParticle } from "./model-particles";

const flow = (patch = {}) => ({ type: "http-request", accepted: 250, rejected: 0, response: 250, errorResponse: 0, latencyMs: 50, ...patch });

describe("model particles", () => {
  it("uses the prototype period clamp(1400 + latency·12, 800, 6000) ms", () => {
    expect(particleDuration(0)).toBe(1400);
    expect(particleDuration(50)).toBe(2000);
    expect(particleDuration(1000)).toBe(6000);
    expect(particleDuration(-100)).toBe(800);
  });

  it("caps particles at five per kind on a link", () => {
    expect(particleCount(1)).toBe(1);
    expect(particleCount(250)).toBe(3);
    expect(particleCount(1e9)).toBe(5);
  });

  it("colours accepted by port type and errors pink, with round trips for answered requests", () => {
    const particles = linkParticles(flow({ rejected: 40, errorResponse: 100, response: 150 }));
    const accepted = particles.filter((p) => p.kind === "accepted");
    expect(accepted).toHaveLength(3);
    expect(accepted[0].color).toBe(portColor("http-request"));
    expect(accepted.filter((p) => p.roundTrip)).toHaveLength(2);
    expect(particles.filter((p) => p.kind !== "accepted").every((p) => p.color === ERROR_COLOR)).toBe(true);
    expect(particles.some((p) => p.kind === "error-response")).toBe(true);
    expect(linkParticles(flow({ accepted: 0, response: 0 }))).toEqual([]);
  });

  it("moves forward, bounces rejected at 55 % and returns error responses", () => {
    const base: FlowParticle = { kind: "accepted", ordinal: 0, count: 1, duration: 1000, roundTrip: false, dwell: .1, amount: 1, color: "#fff" };
    expect(particleProgress(base, 250).progress).toBeCloseTo(.25);
    expect(particleProgress({ ...base, kind: "rejected" }, 275)).toEqual({ progress: .5, returning: false });
    expect(particleProgress({ ...base, kind: "rejected" }, 775).returning).toBe(true);
    expect(particleProgress({ ...base, kind: "error-response" }, 250)).toEqual({ progress: .75, returning: true });
    const trip = { ...base, roundTrip: true };
    expect(particleProgress(trip, 450).progress).toBeCloseTo(1);
    expect(particleProgress(trip, 900).returning).toBe(true);
    expect(particleProgress({ ...base, count: 3, ordinal: 1 }, 0, true).progress).toBeCloseTo(.5);
  });
});
