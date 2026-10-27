// Převedeno z prototypu `test/workflow-model.test.mjs`; vynecháno: nic.
import { describe, expect, it } from "vitest";
import { workflowStep } from "./workflow-model";

const base = { maxActive: 1000, dispatchRps: 100, retryLimit: 1, backoffTicks: 2, timeoutTicks: 100, cancellationRate: 0, preferenceBlockRate: 0, reconciliationRate: .5, failurePolicy: "retry", timerAuthority: "server", externalDelayMs: 0 };
const near = (a: number, b: number) => expect(Math.abs(a - b), `${a} != ${b}`).toBeLessThan(1e-7);
const step = (c: any, input: any, old?: any): any => workflowStep(c, input, old);

function checkConservation(s: any) {
  near(s.totals.accepted - s.totals.terminal, s.active);
  near(s.totals.terminal - s.totals.emitted, s.pendingEvents);
  near(s.queued + s.held + s.inflight, s.active);
  for (const b of s.batches) { expect(Number.isFinite(b.amount) && b.amount > 0).toBe(true); expect(b.attempt).toBeGreaterThanOrEqual(0); }
}

describe("workflow-model", () => {
  it("Dispatch waits for downstream feedback and preview replays current step without consuming work", () => {
    let s = step(base, { offered: 120, tick: 1, hasWorker: true });
    expect(s.dispatched).toBe(100); expect(s.queued).toBe(20); expect(s.succeeded).toBe(0); expect(s.active).toBe(120); checkConservation(s);
    const before = structuredClone(s), p = step(base, { offered: 120, tick: 1, hasWorker: true, preview: true }, s);
    expect(s).toEqual(before); expect(p).toEqual(s);
    s = step(base, { tick: 2, feedback: 1, hasWorker: true }, s);
    expect(s.succeeded).toBe(100); expect(s.dispatched).toBe(20); expect(s.active).toBe(20);
    s = step(base, { tick: 3, feedback: 1, hasWorker: true }, s);
    expect(s.succeeded).toBe(20); expect(s.active).toBe(0); checkConservation(s);
  });
  it("Failed work retries only after backoff, preserves partial success, and exhausts at the configured attempt count", () => {
    let s = step(base, { offered: 100, tick: 1, hasWorker: true });
    s = step(base, { tick: 2, feedback: .25, hasWorker: true }, s);
    expect(s.succeeded).toBe(25); expect(s.retried).toBe(75); expect(s.dispatched).toBe(0); expect(s.queued).toBe(75);
    s = step(base, { tick: 3, feedback: 1, hasWorker: true }, s); expect(s.dispatched).toBe(0);
    s = step(base, { tick: 4, feedback: 1, hasWorker: true }, s); expect(s.dispatched).toBe(75);
    s = step(base, { tick: 5, feedback: 0, hasWorker: true }, s);
    expect(s.exhausted).toBe(75); expect(s.retried).toBe(0); expect(s.active).toBe(0); expect(s.totals.dispatched).toBe(175); checkConservation(s);
  });
  it("Compensation is a terminal modeled outcome, not a fabricated successful retry", () => {
    const c = { ...base, failurePolicy: "compensate" };
    let s = step(c, { offered: 100, tick: 1, hasWorker: true });
    s = step(c, { tick: 2, feedback: .4, hasWorker: true }, s);
    expect(s.succeeded).toBe(40); expect(s.compensated).toBe(60); expect(s.retried).toBe(0); expect(s.active).toBe(0); expect(s.terminal).toBe(100); checkConservation(s);
  });
  it("Blocked preferences reconcile only in following steps; cancellations free admission capacity", () => {
    const c = { ...base, maxActive: 50, cancellationRate: .2, preferenceBlockRate: 1 };
    let s = step(c, { offered: 100, tick: 1, hasWorker: true });
    expect(s.canceled).toBe(20); expect(s.admitted).toBe(70); expect(s.overflow).toBe(30); expect(s.held).toBe(50); expect(s.dispatched).toBe(0);
    s = step(c, { tick: 2, hasWorker: true }, s);
    expect(s.released).toBe(25); expect(s.dispatched).toBe(25); expect(s.held).toBe(25); checkConservation(s);
  });
  it("Server timers expire during an outage, client timers pause while preserving captured feedback", () => {
    for (const timerAuthority of ["server", "client"]) {
      const c = { ...base, timerAuthority, timeoutTicks: 3, externalDelayMs: 1000 };
      let s = step(c, { offered: 100, tick: 1, hasWorker: true });
      for (let tick = 2; tick <= 4; tick++) s = step(c, { tick, failed: true, feedback: 1, hasWorker: true }, s);
      if (timerAuthority === "server") { expect(s.active).toBe(0); expect(s.totals.timedOut).toBe(100); }
      else {
        expect(s.clock).toBe(1); expect(s.active).toBe(100);
        s = step(c, { tick: 5, feedback: 0, hasWorker: true }, s);
        expect(s.succeeded).toBe(100); expect(s.active).toBe(0);
      }
      checkConservation(s);
    }
  });
  it("Absent worker queues until deadline; external delay cannot bypass workflow age limits", () => {
    const c = { ...base, timeoutTicks: 2 };
    let s = step(c, { offered: 100, tick: 1 });
    expect(s.dispatched).toBe(0);
    s = step(c, { tick: 2 }, s); expect(s.timedOut).toBe(0);
    s = step(c, { tick: 3 }, s); expect(s.timedOut).toBe(100); expect(s.active).toBe(0); checkConservation(s);
    const delayed = { ...base, timeoutTicks: 3, externalDelayMs: 5000 };
    s = step(delayed, { offered: 100, tick: 1, hasWorker: true });
    for (let tick = 2; tick <= 4; tick++) s = step(delayed, { tick, feedback: 1, hasWorker: true }, s);
    expect(s.succeeded).toBe(0); expect(s.totals.timedOut).toBe(100); checkConservation(s);
  });
  it("Fixed mixed workload is repeatable and conserves volume through failures, retries, filtering and timeouts", () => {
    const c = { ...base, maxActive: 175, dispatchRps: 42, retryLimit: 3, timeoutTicks: 9, cancellationRate: .1, preferenceBlockRate: .3, reconciliationRate: .4, externalDelayMs: 1800 };
    let a: any, b: any;
    for (let tick = 1; tick <= 80; tick++) {
      const input = { tick, offered: tick < 35 ? 57.5 : 0, feedback: tick % 4 ? .75 : 0, failed: tick >= 12 && tick <= 16, hasWorker: tick !== 27 };
      a = step(c, input, a); b = step(c, input, b);
      expect(a).toEqual(b); checkConservation(a);
    }
    near(a.active, 0); near(a.totals.accepted, a.totals.terminal);
  });
  it("Expired outcomes during outage remain in an outbox until recovery; supplied capacity never exceeds dispatch budget", () => {
    const c = { ...base, timeoutTicks: 1 };
    let s = step(c, { tick: 1, offered: 200, capacity: 1000, hasWorker: true });
    expect(s.dispatched).toBe(100);
    s = step(c, { tick: 2, failed: true, hasWorker: true }, s);
    expect(s.timedOut).toBe(200); expect(s.eventOut).toBe(0); expect(s.pendingEvents).toBe(200); checkConservation(s);
    s = step(c, { tick: 3, hasWorker: true }, s);
    expect(s.eventOut).toBe(200); expect(s.pendingEvents).toBe(0); checkConservation(s);
    s = step(c, { tick: 4, hasWorker: true }, s);
    expect(s.eventOut).toBe(0); checkConservation(s);
  });
});
