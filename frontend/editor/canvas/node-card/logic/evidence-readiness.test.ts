import { describe, expect, it } from "vitest";
import type { CompletionEvidence } from "../components/CardEvidence";
import { batchConfirmable, evidenceReadiness, missingLabel, needsRealTests } from "./evidence-readiness";

const run = (exitCode = 0) => ({ checkId: "unit", command: "npm test", exitCode, logUrl: "", at: "2026-10-07T12:00:00Z" });
const proof = (status: CompletionEvidence["tests"]["status"], url = "") => ({ status, url, note: status === "not_applicable" ? "N/A" : "" });
const evidence = (over: Partial<CompletionEvidence> = {}): CompletionEvidence => ({
  tests: proof("passed"), review: proof("passed", "https://git.example/pr/1"), merge: proof("passed", "https://git.example/pr/1"),
  checksRun: [run()], ...over,
});

describe("evidenceReadiness", () => {
  it("treats missing evidence as not ready with every part missing", () => {
    const value = evidenceReadiness(undefined);
    expect(value.ready).toBe(false);
    expect(missingLabel(value)).toBe("chybí důkazy: tests, review, merge, checksRun");
  });

  it("accepts passed tests without a link when a local run exited 0", () => {
    expect(evidenceReadiness(evidence())).toEqual({ ready: true, missing: [], notApplicable: [] });
  });

  it("rejects passed tests without link and without runs", () => {
    expect(evidenceReadiness(evidence({ checksRun: [] })).missing).toEqual(["tests", "checksRun"]);
  });

  it("lists pending parts and failed runs", () => {
    const value = evidenceReadiness(evidence({ review: proof("pending"), merge: proof("failed", "https://x.example"), checksRun: [run(1)] }));
    expect(value.missing).toEqual(["review", "merge", "checksRun"]);
  });

  it("allows N/A on plain cards but reports it", () => {
    const value = evidenceReadiness(evidence({ tests: proof("not_applicable"), merge: proof("not_applicable"), checksRun: [] }), { name: "Research" });
    expect(value).toEqual({ ready: true, missing: [], notApplicable: ["tests", "merge"] });
    expect(batchConfirmable(value)).toBe(false);
  });

  it("forbids N/A tests and merge on [task] cards and cards with checks", () => {
    const value = evidence({ merge: proof("not_applicable") });
    expect(evidenceReadiness(value, { name: "[task] Build" }).missing).toEqual(["merge"]);
    expect(evidenceReadiness(value, { name: "Build", checks: [{ id: "c", command: "npm test" }] }).ready).toBe(false);
    expect(evidenceReadiness(evidence({ review: proof("not_applicable") }), { name: "[task] Build" }).ready).toBe(true);
  });

  it("detects code-building cards", () => {
    expect(needsRealTests({ name: "[task] X" })).toBe(true);
    expect(needsRealTests({ name: "[research] X" })).toBe(false);
    expect(needsRealTests(undefined)).toBe(false);
  });

  it("allows batch confirmation only for ready evidence without N/A", () => {
    expect(batchConfirmable(evidenceReadiness(evidence()))).toBe(true);
    expect(batchConfirmable(evidenceReadiness(undefined))).toBe(false);
  });
});
