import { expect, it } from "vitest";
import type { FlowRun, FlowVersion, FlowWorkflow, Stall } from "@/shared/flow-editor/logic/flow-types";
import { heartPipelineSummary } from "./heart-pipeline";

const workflow = { id: "w", kind: "heart", project_id: null, name: "Srdce v1" } as FlowWorkflow;
const version = (id: string, n: number, status: FlowVersion["status"]) => ({ id, n, status }) as FlowVersion;
const run = (id: string) => ({ id }) as FlowRun;
const stall = (versionId: string) => ({ workflow_version_id: versionId }) as Stall;

it("shrne aktivní verzi, běhy a jen vlastní prostoje srdce", () => {
  expect(heartPipelineSummary(workflow, [version("a", 1, "retired"), version("b", 2, "active")], [run("r1"), run("r2")],
    [stall("b"), stall("cizi")])).toEqual({ name: "Srdce v1", scope: "sdílené workflow", active: "v2", runs: "2", stalls: 1 });
});

it("bez workflow nic neukazuje, bez aktivní verze to řekne a plný výpis běhů označí plusem", () => {
  expect(heartPipelineSummary(null, [], [], [])).toBeNull();
  const own = { ...workflow, project_id: "p" };
  const summary = heartPipelineSummary(own, [version("a", 1, "draft")], Array.from({ length: 50 }, (_, i) => run(String(i))), []);
  expect(summary).toMatchObject({ scope: "workflow projektu", active: "bez aktivní verze", runs: "50+", stalls: 0 });
});
