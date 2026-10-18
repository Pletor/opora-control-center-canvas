import { describe, expect, it } from "vitest";
import type { CardPipeline, PipelineStage } from "@/editor/workflow/card-pipeline/logic/pipeline-model";
import type { CompletionEvidence } from "../components/CardEvidence";
import { proofSentence, proofSlots } from "./card-proofs";

const stage = (id: string, over: Partial<PipelineStage> = {}): PipelineStage => ({
  id, kind: "work", lens: "", title: id, brief: "", status: "todo", note: "", by: "agent", approved: true, doneBy: "", at: "", ...over,
});
const pipe = (items: PipelineStage[]): CardPipeline => ({ profile: "code", items });
const proof = (status: CompletionEvidence["tests"]["status"], url = "", note = "") => ({ status, url, note });
const run = (checkId: string, exitCode = 0, command = checkId) => ({ checkId, command, exitCode, logUrl: "", at: "2026-10-15T06:00:00Z" });
const evidence = (over: Partial<CompletionEvidence> = {}): CompletionEvidence => ({
  tests: proof("pending"), review: proof("pending"), merge: proof("pending"), checksRun: [], ...over,
});
const statuses = (slots: ReturnType<typeof proofSlots>) => slots.map((s) => s.status);

describe("proofSlots", () => {
  it("keeps four fixed slots in order even without evidence or pipeline", () => {
    const slots = proofSlots(undefined, undefined, undefined);
    expect(slots.map((s) => s.key)).toEqual(["tests", "security", "review", "merge"]);
    expect(statuses(slots)).toEqual(["none", "none", "none", "none"]);
    expect(proofSentence(slots)).toBe("Doklady: Testy nedoloženo, Security nedoloženo, Review nedoloženo, Merge nedoloženo");
  });

  it("proves tests only with a run or link and every card check green", () => {
    const checks = [{ id: "pytest", command: "pytest" }, { id: "e2e", command: "playwright test" }];
    const local = evidence({ tests: proof("passed"), checksRun: [run("pytest"), run("e2e", 0, "playwright test")] });
    expect(proofSlots(local, checks, undefined)[0]).toMatchObject({ status: "proven", title: "Testy · doklad přiložen (server neověřuje) · ✓ pytest, ✓ e2e" });
    const missingE2e = evidence({ tests: proof("passed"), checksRun: [run("pytest")] });
    expect(proofSlots(missingE2e, checks, undefined)[0]).toMatchObject({ status: "declared", title: "Testy · deklarováno bez dokladu · ✓ pytest, … e2e" });
    const link = evidence({ tests: proof("passed", "https://ci.example/run") });
    expect(statuses(proofSlots(link, [], undefined))[0]).toBe("proven");
    expect(statuses(proofSlots(evidence({ tests: proof("passed") }), [], undefined))[0]).toBe("declared");
  });

  it("fails tests on a failed run or proof and marks not applicable with its reason", () => {
    expect(proofSlots(evidence({ tests: proof("passed"), checksRun: [run("ruff", 1)] }), [], undefined)[0].status).toBe("failed");
    // Opakování testu právě běží: slot pulsuje i přes selhaný důkaz z minula.
    const retry = pipe([stage("t", { kind: "test", status: "failed" }), stage("f", { kind: "fix", status: "passed" }), stage("t2", { kind: "test", status: "doing", retryOf: "t" })]);
    expect(proofSlots(evidence({ tests: proof("failed"), checksRun: [run("ruff", 1)] }), [], retry)[0].status).toBe("running");
    const linkMissingCheck = evidence({ tests: proof("passed", "https://ci.example/run") });
    expect(proofSlots(linkMissingCheck, [{ id: "e2e", command: "playwright test" }], undefined)[0]).toMatchObject({ status: "declared", title: "Testy · deklarováno bez dokladu · … e2e" });
    expect(proofSlots(evidence({ tests: proof("failed") }), [], undefined)[0].status).toBe("failed");
    const na = proofSlots(evidence({ tests: proof("not_applicable", "", "výzkum") }), [], undefined)[0];
    expect(na).toMatchObject({ status: "na", title: "Testy · nevztahuje se · výzkum" });
  });

  it("reads a passed test stage without evidence as declared and a running one as running", () => {
    const passed = pipe([stage("w", { status: "passed" }), stage("t", { kind: "test", status: "passed" })]);
    expect(statuses(proofSlots(undefined, [], passed))[0]).toBe("declared");
    const doing = pipe([stage("w", { status: "passed" }), stage("t", { kind: "test", status: "doing" })]);
    expect(statuses(proofSlots(undefined, [], doing))[0]).toBe("running");
  });

  it("derives security from the hacker critic: passed, running, stuck or absent", () => {
    const passed = pipe([stage("w", { status: "passed" }), stage("h", { kind: "critic", lens: "hacker", status: "passed", doneBy: "critic-1" })]);
    expect(proofSlots(undefined, [], passed)[1]).toMatchObject({ status: "proven", title: "Security · doklad přiložen (server neověřuje) · kritik hacker prošel · critic-1" });
    const stuck = pipe([stage("w", { status: "passed" }), stage("h", { kind: "critic", lens: "hacker", status: "failed" })]);
    expect(statuses(proofSlots(undefined, [], stuck))[1]).toBe("failed");
    const retried = pipe([stage("w", { status: "passed" }), stage("h", { kind: "critic", lens: "hacker", status: "failed" }),
      stage("f", { kind: "fix", status: "todo" }), stage("h2", { kind: "critic", lens: "hacker", status: "todo", retryOf: "h" })]);
    expect(statuses(proofSlots(undefined, [], retried))[1]).toBe("none");
    const sly = pipe([stage("s", { kind: "critic", lens: "sly", status: "passed" })]);
    expect(statuses(proofSlots(undefined, [], sly))[1]).toBe("none");
    // Starší úspěch nedokládá novější audit: po selhání druhého kritika rozhoduje až jeho opakování.
    const older = pipe([stage("h1", { kind: "critic", lens: "hacker", status: "passed" }), stage("w2", { status: "passed" }),
      stage("h2", { kind: "critic", lens: "hacker", status: "failed" }), stage("f", { kind: "fix" }),
      stage("h3", { kind: "critic", lens: "hacker", retryOf: "h2" })]);
    expect(statuses(proofSlots(undefined, [], older))[1]).toBe("none");
    const rerun = pipe([...older.items.slice(0, 4), stage("h3", { kind: "critic", lens: "hacker", retryOf: "h2", status: "doing" })]);
    expect(statuses(proofSlots(undefined, [], rerun))[1]).toBe("running");
  });

  it("proves review and merge only with a link; passed without a link is declared", () => {
    const linked = evidence({ review: proof("passed", "https://git.example/pr/1"), merge: proof("passed", "https://git.example/commit/a") });
    expect(statuses(proofSlots(linked, [], undefined)).slice(2)).toEqual(["proven", "proven"]);
    const bare = evidence({ review: proof("passed"), merge: proof("passed") });
    expect(statuses(proofSlots(bare, [], undefined)).slice(2)).toEqual(["declared", "declared"]);
    const reviewStage = pipe([stage("w", { status: "passed" }), stage("r", { kind: "review", status: "passed" })]);
    expect(statuses(proofSlots(undefined, [], reviewStage))[2]).toBe("declared");
    expect(statuses(proofSlots(evidence({ merge: proof("failed", "https://x.example") }), [], undefined))[3]).toBe("failed");
  });
});
