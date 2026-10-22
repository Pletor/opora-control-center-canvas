import { describe, expect, it } from "vitest";
import { parseSpec, renderStage } from "./stage-render";
import { LENS_SPEC } from "./lens-fixture";
import { focusBoxes, stageFlow, stagesOf, stepStage, walkKey, walkReducer, type Atlas } from "./walkthrough";

const parsed = parseSpec(LENS_SPEC);
const doc = parsed.doc!;

describe("stages and walkthrough", () => {
  it("parses the fixture with the PR Lens schema and refuses a broken spec", () => {
    expect(parsed.error).toBe("");
    const broken = parseSpec({ ...LENS_SPEC, edges: [{ id: "x", from: "nope", to: "merge-head", kind: "call", delta: "added" }] });
    expect(broken.doc).toBeNull();
    expect(broken.error).not.toBe("");
  });
  it("lists the document's views as stages and resolves a step's stage", () => {
    const stages = stagesOf(doc);
    expect(stages.map(stage => stage.key)).toEqual(["view:overview", "view:sequence"]);
    const steps = doc.walkthrough!.steps;
    expect(stepStage(doc, steps[0], stages[0], stages).key).toBe("view:sequence"); // the view that shows only that flow
    expect(stepStage(doc, steps[1], stages[1], stages).key).toBe("view:overview");
    expect(stepStage(doc, steps[2], stages[1], stages).key).toBe("view:sequence"); // no stage: stays
    expect(stepStage(doc, steps[0], stages[0], stages.slice(0, 1))).toMatchObject({ key: "flow:pinned-merge", lens: "data-flow", flow: "pinned-merge" });
    expect(stagesOf({ ...doc, views: [] }).map(stage => stage.key)).toEqual(["lens:architecture", "lens:data-flow"]);
  });
  it("renders every stage in both themes and finds the focus boxes in its atlas", () => {
    const stages = stagesOf(doc), steps = doc.walkthrough!.steps;
    for (const theme of ["light", "dark"] as const) for (const stage of stages) {
      const drawn = renderStage(doc, stage, theme);
      expect("svg" in drawn && drawn.svg.startsWith("<svg")).toBe(true);
    }
    const flowStage = stepStage(doc, steps[0], stages[0], []);
    const flowDrawn = renderStage(doc, flowStage, "dark") as { atlas: Atlas };
    expect(focusBoxes(steps[0], flowDrawn.atlas, stageFlow(flowStage, steps[0]))).toHaveLength(1);
    const arch = renderStage(doc, stages[0], "light") as { atlas: Atlas };
    expect(focusBoxes(steps[1], arch.atlas, null)).toHaveLength(2);
    expect(focusBoxes(steps[2], arch.atlas, null)).toEqual([]);
    expect(renderStage(doc, { key: "x", label: "x", lens: "architecture", view: "missing" }, "light")).toHaveProperty("error");
  });
  it("escapes agent text in the SVG it draws", () => {
    const hostile = parseSpec({ ...LENS_SPEC, title: "<script>alert(1)</script>",
      nodes: LENS_SPEC.nodes.map((node, index) => index ? node : { ...node, label: '"><img src=x onerror=alert(1)>' }) });
    const drawn = renderStage(hostile.doc!, stagesOf(hostile.doc!)[0], "light") as { svg: string };
    expect(drawn.svg).not.toContain("<script>");
    expect(drawn.svg).not.toContain("<img");
  });
  it("plays forward and back, stops on Esc and only takes arrows while playing", () => {
    let walk = { index: -1 };
    walk = walkReducer(walk, "next", 3);
    expect(walk.index).toBe(0);
    walk = walkReducer(walkReducer(walk, "next", 3), "next", 3);
    expect(walk.index).toBe(2);
    expect(walkReducer(walk, "next", 3).index).toBe(2);
    expect(walkReducer(walk, "prev", 3).index).toBe(1);
    expect(walkReducer({ index: 0 }, "prev", 3).index).toBe(0);
    expect(walkReducer(walk, "stop", 3).index).toBe(-1);
    expect(walkReducer({ index: -1 }, "start", 0).index).toBe(-1);
    expect(walkKey("w", false)).toBe("next");
    expect(walkKey("ArrowRight", false)).toBeNull();
    expect(walkKey("ArrowLeft", true)).toBe("prev");
    expect(walkKey("Escape", true)).toBe("stop");
  });
});
