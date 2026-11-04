import { describe, expect, it } from "vitest";
import { activityOf, barText, isActive, opensDetail, ownedWork, SETTLE_MS, STALL_MS, stepTime, workPhase } from "./heart-work";
import { answeredOnly, failed, FLOW, idleStatus, message, running, SENT, STEPS } from "./heart-work.fixtures";

const phase = (status: ReturnType<typeof running> | null, extra: { now?: number; seen?: number | null } = {}) =>
  workPhase({ work: ownedWork(status, FLOW, SENT), status, sentAt: SENT, now: extra.now ?? SENT + 10_000, finishedSeenAt: extra.seen ?? null });

describe("heart work", () => {
  it("recognizes only our message: same flow, sent after the submit", () => {
    expect(ownedWork(running(), FLOW, SENT)?.running).toBe(true);
    expect(ownedWork(running(), "other", SENT)).toBeNull();
    const old = { ...running(), current: { startedAt: "2026-11-04T09:00:00Z", inputs: [message(FLOW, "2026-11-04T09:00:00Z")] } };
    expect(ownedWork(old, FLOW, SENT)).toBeNull();
    expect(ownedWork(idleStatus(), FLOW, SENT)).toBeNull();
  });
  it("walks queued, running, finishing, then the outcome", () => {
    expect(phase(idleStatus())).toBe("queued");
    expect(phase({ ...idleStatus(), running: true })).toBe("queued");
    expect(phase(running())).toBe("running");
    expect(phase(answeredOnly())).toBe("finishing");
    expect(phase(answeredOnly(), { seen: SENT, now: SENT + 1000 })).toBe("finishing");
    expect(phase(answeredOnly(), { seen: SENT, now: SENT + SETTLE_MS })).toBe("done-no-draw");
    expect(phase(failed(), { seen: SENT, now: SENT + SETTLE_MS })).toBe("error");
  });
  it("reports a stall only when nothing runs for 3 minutes", () => {
    expect(phase(idleStatus(), { now: SENT + STALL_MS })).toBe("stalled");
    expect(phase({ ...idleStatus(), running: true }, { now: SENT + STALL_MS })).toBe("queued");
    expect(phase(null, { now: SENT + STALL_MS })).toBe("stalled");
  });
  it("carries reply, error and the missing steps of an old batch", () => {
    expect(ownedWork(answeredOnly(), FLOW, SENT)?.reply).toContain("tabulky");
    expect(ownedWork(failed(), FLOW, SENT)).toMatchObject({ failed: true, error: "Limit předplatného vyčerpán do 12:00." });
    const old = answeredOnly();
    delete old.batches[0].steps;
    expect(ownedWork(old, FLOW, SENT)?.steps).toBeNull();
  });
  it("tells the activity from the last step", () => {
    expect(activityOf(null)).toBe("pracuje");
    expect(activityOf(STEPS.slice(0, 1))).toBe("přemýšlí");
    expect(activityOf(STEPS.slice(0, 3))).toBe("čte skill");
    expect(activityOf(STEPS)).toBe("zjišťuje druhy uzlů");
    expect(activityOf([{ t: 0, kind: "tool", text: "python opora_heart.py library case f" }])).toBe("zkouší případ");
    expect(activityOf([{ t: 0, kind: "tool", text: "ls" }])).toBe("pracuje");
  });
  it("writes the bar line with step count and the typical duration", () => {
    const work = ownedWork(running(STEPS.slice(0, 3)), FLOW, SENT);
    expect(barText("running", work, 12_000, 60_000)).toBe("Srdce čte skill… 12 s · krok 3 · obvykle ~60 s");
    expect(barText("running", work, 12_000, null)).toBe("Srdce čte skill… 12 s · krok 3");
    expect(barText("queued", null, 4000, 60_000)).toBe("Srdce se probouzí… 4 s");
  });
  it("opens the detail window only for a finished batch; polls only while active", () => {
    expect([opensDetail("done-no-draw"), opensDetail("error"), opensDetail("running"), opensDetail("stalled")]).toEqual([true, true, false, false]);
    expect([isActive("queued"), isActive("finishing"), isActive("error"), isActive("stalled")]).toEqual([true, true, false, false]);
    expect(stepTime(85_000)).toBe("1:25");
  });
});
