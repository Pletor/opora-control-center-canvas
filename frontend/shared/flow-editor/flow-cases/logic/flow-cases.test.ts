import { describe, expect, it } from "vitest";
import { processGraph } from "../../logic/flow-fixtures";
import { addCase, caseFingerprint, caseFromDraft, caseMark, draftOf, removeCase, setCase } from "./flow-cases";

describe("flow cases", () => {
  it("adds a case starting at the first node and numbers it past existing ids", () => {
    const { graph, added } = addCase({ ...processGraph(), cases: [] });
    expect(added).toMatchObject({ id: "case-1", name: "Případ 1", start: "formular", input: {} });
    expect(addCase(graph).added.id).toBe("case-2");
    expect(removeCase(graph, "case-1").cases).toEqual([]);
  });

  it("round-trips a case through its text draft", () => {
    const flowCase = processGraph().cases![0];
    expect(caseFromDraft(flowCase.id, draftOf(flowCase))).toEqual({ case: flowCase });
    expect(setCase(processGraph(), { ...flowCase, name: "Jiné" }).cases![0].name).toBe("Jiné");
  });

  it("refuses invalid JSON, wrong shape and a missing name or start without saving", () => {
    const draft = draftOf(processGraph().cases![0]);
    expect(caseFromDraft("x", { ...draft, input: "{" })).toMatchObject({ error: expect.stringContaining("Vstup: neplatný JSON") });
    expect(caseFromDraft("x", { ...draft, expect: "[1]" })).toEqual({ error: "Očekávání: čekám objekt { … }." });
    expect(caseFromDraft("x", { ...draft, env: "nope" })).toMatchObject({ error: expect.stringContaining("Prostředí") });
    expect(caseFromDraft("x", { ...draft, name: " " })).toEqual({ error: "Případ potřebuje jméno." });
    expect(caseFromDraft("x", { ...draft, start: "" })).toEqual({ error: "Vyberte start (uzel, kde případ začíná)." });
  });

  it("drops empty env and expect and defaults an empty input to {}", () => {
    const result = caseFromDraft("x", { name: "A", description: "", start: "formular", input: "", env: "", expect: "" });
    expect(result).toEqual({ case: { id: "x", name: "A", start: "formular", input: {} } });
  });

  it("marks green on match, red on mismatch, grey when not run, without expect or stale", () => {
    const graph = processGraph(), flowCase = graph.cases![0], fingerprint = caseFingerprint(graph, flowCase);
    expect(caseMark({ fingerprint, ok: true }, fingerprint)).toBe("ok");
    expect(caseMark({ fingerprint, ok: false }, fingerprint)).toBe("fail");
    expect(caseMark({ fingerprint, ok: null }, fingerprint)).toBe("idle");
    expect(caseMark(undefined, fingerprint)).toBe("idle");
    expect(caseMark({ fingerprint, ok: true }, caseFingerprint(graph, { ...flowCase, input: { vyska: 1 } }))).toBe("idle");
  });
});
