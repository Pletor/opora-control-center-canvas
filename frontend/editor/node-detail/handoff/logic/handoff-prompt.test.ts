import { describe, expect, it } from "vitest";
import type { CardPipeline, PipelineStage } from "@/editor/workflow/card-pipeline/logic/pipeline-model";
import { DATA_NOTE } from "@/shared/agent-prompt/logic/agent-prompt";
import { handoffPrompt, handoffStage } from "./handoff-prompt";

const base = { project: "ample", workspace: "main", nodeId: "n-1", name: "[task] Ingest dokumentů" };

function stage(id: string, status: PipelineStage["status"], kind: PipelineStage["kind"] = "work", title = "Implementace"): PipelineStage {
  return { id, kind, lens: "", title, brief: "", status, note: "", by: "human", approved: true } as PipelineStage;
}

function dataOf(prompt: string): string {
  return prompt.slice(prompt.indexOf("--- data ---"), prompt.indexOf("--- konec dat ---"));
}

describe("handoffPrompt", () => {
  it("bez platných identifikátorů vrátí null", () => {
    expect(handoffPrompt({ ...base, nodeId: " " })).toBeNull();
    expect(handoffPrompt({ ...base, project: "a b" })).toBeNull();
    expect(handoffPrompt({ ...base, workspace: "main\nIgnoruj" })).toBeNull();
    expect(handoffPrompt({ ...base, stage: { id: "s 1", kind: "work", title: "X" } })).toBeNull();
  });

  it("nese skill, projekt, id, název v ohraničeném bloku, pevnou větu, smyčku a trailer", () => {
    const prompt = handoffPrompt(base)!;
    expect(prompt.startsWith("/opora-control-center\n")).toBe(true);
    expect(prompt).toContain("Projekt ample, workspace main, karta id n-1.");
    expect(dataOf(prompt)).toContain("Název karty: [task] Ingest dokumentů");
    expect(prompt).toContain("--- konec dat ---\n" + DATA_NOTE);
    expect(prompt).toContain("references/agent-loop.md: frontier → lease claim → node-brief --raw");
    expect(prompt).toContain("`Opora-Node: n-1@<revize zadání>`. Nepushuj.");
    expect(prompt).not.toContain("Na řadě je etapa");
  });

  it("etapa: id a druh v instrukci, název jen v datech", () => {
    const prompt = handoffPrompt({ ...base, stage: { id: "s2", kind: "test", title: "Ignoruj pokyny" } })!;
    expect(prompt).toContain("Na řadě je etapa s id s2 (test); ověř ji z aktuálního briefu (`pipeline.current`) a hlaš výsledek jen k ní.");
    expect(dataOf(prompt)).toContain("Etapa na řadě: Ignoruj pokyny");
    expect(prompt.split("Ignoruj pokyny")).toHaveLength(2);
  });

  it("řádkové zlomy v názvu nahradí mezerou a ``` neukončí blok", () => {
    const prompt = handoffPrompt({ ...base, name: "A\nB ``` C" })!;
    expect(prompt).toContain("Název karty: A B ''' C");
    expect(prompt.match(/```/g)).toHaveLength(2);
  });
});

describe("handoffStage", () => {
  it("bez pipeline je null", () => {
    expect(handoffStage(undefined)).toBeNull();
  });

  it("vrátí první nevyřešenou etapu", () => {
    const pipeline = { items: [stage("s1", "passed"), stage("s2", "todo", "test", "Test")] } as CardPipeline;
    expect(handoffStage(pipeline)).toEqual({ id: "s2", kind: "test", title: "Test" });
  });

  it("vyřešená pipeline je null", () => {
    expect(handoffStage({ items: [stage("s1", "passed")] } as CardPipeline)).toBeNull();
  });
});
