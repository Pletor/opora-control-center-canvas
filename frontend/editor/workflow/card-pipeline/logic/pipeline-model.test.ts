import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { emptyDesktopState, type DesktopState } from "@/shared/desktop-state/logic/types";
import PipelineBlock from "@/editor/workflow/card-pipeline/components/PipelineBlock";
import {
  moveStage, pipelineOf, pipelineSummary, removeStage, switchNeedsConfirm, toggleSkip,
  type CardPipeline, type PipelineStage,
} from "@/editor/workflow/card-pipeline/logic/pipeline-model";

const stage = (id: string, kind: PipelineStage["kind"], extra: Partial<PipelineStage> = {}): PipelineStage => ({
  id, kind, lens: kind === "critic" ? "hacker" : "", title: `Etapa ${id}`, brief: "", status: "todo", note: "",
  by: "agent", approved: true, doneBy: "", at: "", ...extra,
});
const routed = (items: PipelineStage[]): CardPipeline => ({ profile: "code", items, routedBy: "router-1", reason: "Kód backendu." });
const withPipeline = (pipeline: CardPipeline): DesktopState => ({ ...emptyDesktopState(), nodes: { n: { phase: "discover" as const, criteria: [], steps: [], stages: pipeline } } });
const block = (pipeline: CardPipeline) => renderToStaticMarkup(createElement(PipelineBlock, {
  pipeline, goal: true, disabled: false, onRoute: async () => true, onMove: () => {}, onRemove: () => {}, onSkip: () => {}, onEdit: async () => true,
}));

describe("pipeline karty", () => {
  it("profil se přepíná jedním klikem, potvrzení chce až rozběhnutá pipeline", () => {
    expect(switchNeedsConfirm(routed([stage("a", "work"), stage("b", "test")]))).toBe(false);
    expect(switchNeedsConfirm(routed([stage("a", "work", { status: "passed" }), stage("b", "test")]))).toBe(true);
    const html = block(routed([stage("a", "work")]));
    expect(html).toContain('aria-pressed="true"');
    expect(html).toContain("Router router-1: Kód backendu.");
    expect(html).not.toContain("<select");
  });

  it("karta bez pipeline čeká na router", () => {
    expect(block({ profile: "custom", items: [] })).toContain("Čeká na router");
  });

  it("úspěšné opakování nahradí selhanou etapu a vyčerpaná smyčka čeká na člověka", () => {
    const healed = pipelineSummary(routed([
      stage("w", "work", { status: "passed" }),
      stage("c", "critic", { status: "failed" }),
      stage("f", "fix", { status: "passed" }),
      stage("r", "critic", { status: "passed", retryOf: "c" }),
    ]));
    expect(healed).toMatchObject({ finished: 4, total: 4, current: null, retries: 1, stuck: [] });
    const stuck = pipelineSummary(routed([stage("w", "work", { status: "passed" }), stage("c", "critic", { status: "failed" })]));
    expect(stuck.stuck.map((s) => s.id)).toEqual(["c"]);
    expect(stuck.current).toBeNull();
  });

  it("člověk přeskočí a vrátí etapu jedním klikem, přeskládá a odebere", () => {
    let state = withPipeline(routed([stage("a", "work"), stage("b", "critic")]));
    state = toggleSkip("n", "b")(state);
    expect(pipelineOf(state, "n").items[1]).toMatchObject({ status: "skipped", doneBy: "člověk" });
    state = toggleSkip("n", "b")(state);
    expect(pipelineOf(state, "n").items[1].status).toBe("todo");
    state = moveStage("n", 1, -1)(state);
    expect(pipelineOf(state, "n").items.map((s) => s.id)).toEqual(["b", "a"]);
    state = removeStage("n", "a")(removeStage("n", "b")(state));
    expect(state.nodes.n.stages).toBeUndefined();
  });
});
