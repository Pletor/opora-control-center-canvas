import { describe, expect, it } from "vitest";
import type { CardPipeline, PipelineStage } from "@/editor/workflow/card-pipeline/logic/pipeline-model";
import { DOT_TITLE, processSentence, processView } from "./card-process";

const stage = (id: string, over: Partial<PipelineStage> = {}): PipelineStage => ({
  id, kind: "work", lens: "", title: id, brief: "", status: "todo", note: "", by: "agent", approved: true, doneBy: "", at: "", ...over,
});
const pipe = (items: PipelineStage[], profile: CardPipeline["profile"] = "code"): CardPipeline => ({ profile, items });

describe("processView", () => {
  it("returns undefined without stages and an unrouted view for an empty pipeline", () => {
    expect(processView(undefined)).toBeUndefined();
    const view = processView(pipe([], "custom"))!;
    expect(view.routed).toBe(false);
    expect(view.dots).toEqual([]);
    expect(view.waitingOnHuman).toBe(false);
  });

  it("marks the first todo after passed stages as current in a code profile", () => {
    const view = processView(pipe([
      stage("w", { status: "passed", doneBy: "a1" }),
      stage("t", { kind: "test", status: "passed" }),
      stage("r", { kind: "review" }),
      stage("c", { kind: "critic", lens: "hacker" }),
    ]))!;
    expect(view.routed).toBe(true);
    expect(view.profileLabel).toBe("Kód");
    expect(view.dots.map((d) => d.current)).toEqual([false, false, true, false]);
    expect([view.finished, view.total]).toEqual([2, 4]);
    expect(view.waitingOnHuman).toBe(false);
  });

  it("keeps a parallel critic round in order with one current stage", () => {
    const view = processView(pipe([
      stage("w", { status: "passed" }),
      stage("c1", { kind: "critic", lens: "user", status: "passed" }),
      stage("c2", { kind: "critic", lens: "sly", status: "doing" }),
      stage("c3", { kind: "critic", lens: "hacker", status: "passed" }),
    ]))!;
    expect(view.dots.map((d) => d.lens)).toEqual(["", "user", "sly", "hacker"]);
    expect(view.dots.filter((d) => d.current).map((d) => d.id)).toEqual(["c2"]);
    expect(view.finished).toBe(3);
  });

  it("flags a failed stage without retry as stuck and waiting on a human", () => {
    const view = processView(pipe([
      stage("w", { status: "passed" }),
      stage("c", { kind: "critic", lens: "hacker", status: "failed", note: "únik tokenu" }),
    ], "security"))!;
    expect(view.dots[1].stuck).toBe(true);
    expect(view.waitingOnHuman).toBe(true);
    expect(DOT_TITLE(view.dots[1])).toContain("Kritik: hacker");
    expect(DOT_TITLE(view.dots[1])).toContain("selhalo");
    expect(DOT_TITLE(view.dots[1])).toContain("únik tokenu");
  });

  it("draws a failed stage replaced by a passed retry and marks the retry", () => {
    const view = processView(pipe([
      stage("t", { kind: "test", status: "failed" }),
      stage("f", { kind: "fix", status: "passed" }),
      stage("t2", { kind: "test", status: "passed", retryOf: "t" }),
    ]))!;
    expect(view.dots.map((d) => d.status)).toEqual(["failed", "passed", "passed"]);
    expect(view.dots.map((d) => d.retry)).toEqual([false, false, true]);
    expect(view.dots.some((d) => d.stuck)).toBe(false);
    expect(view.waitingOnHuman).toBe(false);
    expect([view.finished, view.total]).toEqual([3, 3]);
    expect(DOT_TITLE(view.dots[2])).toContain("↺");
  });

  it("draws only approved stages and counts proposals aside", () => {
    const view = processView(pipe([
      stage("w", { status: "passed" }),
      stage("c", { kind: "critic", lens: "hacker" }),
      stage("x", { kind: "test", approved: false }),
    ]))!;
    expect(view.dots.map((d) => d.id)).toEqual(["w", "c"]);
    expect(view.total).toBe(2);
    expect(view.proposed).toBe(1);
    expect(processSentence(view)).toBe("Proces: 1/2, na řadě Kritik: hacker, 1 ke schválení");
    const onlyProposed = processView(pipe([stage("x", { approved: false })]))!;
    expect(onlyProposed.routed).toBe(false);
    expect(onlyProposed.proposed).toBe(1);
  });

  it("says in one sentence what failed and waits on a human", () => {
    const view = processView(pipe([
      stage("w", { status: "passed" }),
      stage("c", { kind: "critic", lens: "hacker", status: "failed", note: "x" }),
      stage("r", { kind: "review" }),
    ]))!;
    expect(processSentence(view)).toBe("Proces: 1/3, na řadě Review, 1 selhalo, čeká na člověka");
    expect(processSentence(processView(pipe([]))!)).toBe("Proces: čeká na router");
  });
});
