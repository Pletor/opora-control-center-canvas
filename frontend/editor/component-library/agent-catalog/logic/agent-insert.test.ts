import { describe, expect, it } from "vitest";
import { emptyDesktopState, nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import {
  actionFromItem,
  insertActionFromItem,
  insertRulesFromItem,
  PHASE_LABELS,
  phaseNote,
  phasesFromSteps,
  ruleFromItem,
  sectorFromWorkflow,
} from "./agent-insert";
import { agentItemById, type AgentItem } from "./agent-catalog";
import { RELATES_BLOCK_TITLE } from "@/editor/component-library/library-catalog/logic/catalog-insert";
import { itemById } from "@/editor/component-library/library-catalog/logic/library-catalog";

const PHASE_STEPS = [
  { title: "discover", text: "Najdi podklady." },
  { title: "define", text: "Popiš rozhraní." },
  { title: "build", text: "Postav to." },
  { title: "verify", text: "Ověř to." },
  { title: "live", text: "Předej to." },
];

/** Zkušební položka: základ, ke kterému se v testu dopisuje jen to, co se zkouší. */
const fixture = (patch: Partial<AgentItem> = {}): AgentItem => ({
  id: "fixture",
  category: "rules",
  label: "Zkušební postup",
  purpose: "Jen pro test.",
  kind: "rule",
  relates: ["@test-done-gates"],
  invariants: [
    { kind: "must", text: "Musí platit A" },
    { kind: "must_not", text: "Nesmí C" },
  ],
  steps: PHASE_STEPS,
  done: ["Testy prochází."],
  stopCondition: "Chybí podklad.",
  ...patch,
});

const gates = itemById("test-done-gates")!;

describe("agent-insert – pravidla karty", () => {
  it("invarianty se stanou pravidly karty beze změny textu", () => {
    const rules = ruleFromItem(fixture())!;
    expect(rules.map((r) => [r.kind, r.text])).toEqual([
      ["must", "Musí platit A"],
      ["must_not", "Nesmí C"],
    ]);
  });

  it("agent dostane navíc první pravidlo s rolí", () => {
    const rules = ruleFromItem(fixture({ kind: "agent", label: "Subagent Explore: haiku", purpose: "Hledá a čte." }))!;
    expect(rules[0]).toMatchObject({ kind: "must", text: "Role: Subagent Explore: haiku. Hledá a čte." });
    expect(rules.length).toBe(3);
  });

  it("vydaná hranice dá na kartu svou invariantu", () => {
    const rules = ruleFromItem(agentItemById("rule-no-delete-without-preview")!)!;
    expect(rules.map((r) => [r.kind, r.text])).toEqual([["must_not", "Nic se nemaže na první zavolání bez náhledu a potvrzení."]]);
  });

  it("položka info se netáhne: null ze všech tří překladů", () => {
    const info = fixture({ kind: "info" });
    expect(ruleFromItem(info)).toBeNull();
    expect(actionFromItem(info)).toBeNull();
    expect(sectorFromWorkflow(info, null, 0, 0)).toBeNull();
  });
});

describe("agent-insert – akce", () => {
  it("pipeline si drží id a nese účel, kroky, hotovo, stop a souvislosti jako texty", () => {
    const action = actionFromItem(fixture({ kind: "action", id: "pl-feature-folder", steps: [{ title: "A", text: "" }, { title: "B", text: "" }] }))!;
    expect(action.pipelineId).toBe("pl-feature-folder");
    expect(action.params).toEqual({
      purpose: "Jen pro test.",
      steps: "A → B",
      done: "Testy prochází.",
      stopCondition: "Chybí podklad.",
      relates: `${gates.label}: ${gates.purpose}`,
    });
  });

  it("hook bez kroků a hotovo nenese prázdné parametry", () => {
    const action = actionFromItem(agentItemById("hook-restart-backend")!)!;
    expect(Object.keys(action.params).sort()).toEqual(["purpose", "relates"]);
    expect(Object.values(action.params).every((value) => typeof value === "string" && value.length > 0)).toBe(true);
  });
});

describe("agent-insert – sektor z workflow", () => {
  const insert = () => sectorFromWorkflow(fixture({ kind: "workflow" }), "vrstva", 120.4, 40.6)!;

  it("sektor je rám postupu s účelem, invariantami a blokem Souvisí s", () => {
    const { sector, nodes } = insert();
    expect(sector.kind).toBe("sector");
    expect(sector.parentId).toBe("vrstva");
    expect(sector.purpose).toBe("Jen pro test.");
    expect({ x: sector.x, y: sector.y }).toEqual({ x: 120, y: 41 });
    expect(nodes[sector.id].rules.map((r) => r.text)).toEqual(["Musí platit A", "Nesmí C"]);
    expect(nodes[sector.id].blocks.map((b) => [b.title, b.text])).toEqual([[RELATES_BLOCK_TITLE, `- ${gates.label}: ${gates.purpose}`]]);
  });

  it("každá fáze z kroků má vlastní kartu v jedné řadě a vazby next", () => {
    const { sector, children, phases, edges } = insert();
    expect(phases).toEqual(["discover", "define", "build", "verify", "live"]);
    expect(children.map((c) => c.name)).toEqual(["Objevit", "Definovat", "Postavit", "Ověřit", "Provoz"]);
    expect(children.every((c) => c.parentId === sector.id)).toBe(true);
    expect(children.map((c) => c.x)).toEqual([80, 400, 720, 1040, 1360]);
    expect(children[0].purpose).toBe("Najdi podklady.");
    expect(edges.map((e) => [e.source, e.target, e.port])).toEqual(
      children.slice(1).map((child, index) => [children[index].id, child.id, "next"]),
    );
  });

  it("karty nesou svou fázi a kritéria hotovo visí na poslední", () => {
    const { children, nodes } = insert();
    expect(children.map((c) => nodes[c.id].phase)).toEqual(["discover", "define", "build", "verify", "live"]);
    expect(nodes[children[0].id].criteria).toEqual([]);
    expect(nodes[children[4].id].criteria.map((c) => [c.text, c.checked])).toEqual([["Testy prochází.", false]]);
  });

  it("fáze se čtou z názvů kroků; workflow bez nich sektor nedá", () => {
    expect(phasesFromSteps(fixture({ steps: [{ title: "Live", text: "" }, { title: "discover", text: "" }] }))).toEqual(["discover", "live"]);
    expect(sectorFromWorkflow(fixture({ kind: "workflow", steps: [] }), null, 0, 0)).toBeNull();
    expect(phaseNote(fixture(), "verify")).toBe("Ověř to.");
    expect(PHASE_LABELS.live).toBe("Provoz");
  });

  it("vydané workflow „Zadání → hotovo v pěti fázích“ dá sektor s pěti kartami", () => {
    const item = agentItemById("wf-five-phases")!;
    const made = sectorFromWorkflow(item, null, 0, 0)!;
    expect(made.children.length).toBe(5);
    expect(made.edges.length).toBe(4);
    expect(made.children[4].purpose).toBe(item.steps![4].text);
  });
});

describe("agent-insert – vložení do karty", () => {
  it("pravidla se přidají jednou; druhé puštění téže dlaždice kartu nezaplevelí", () => {
    const item = fixture();
    const first = insertRulesFromItem("uzel", item)(emptyDesktopState());
    const second = insertRulesFromItem("uzel", item)(first);
    expect(nodeWorkflowOf(second, "uzel").rules.length).toBe(2);
    expect(nodeWorkflowOf(second, "jiny").rules).toEqual([]);
  });

  it("akce se pozná podle pipelineId, takže se linka nerozdvojí ani po přejmenování", () => {
    const first = insertActionFromItem("uzel", fixture({ kind: "action", id: "pl-feature-folder" }))(emptyDesktopState());
    const second = insertActionFromItem("uzel", fixture({ kind: "action", id: "pl-feature-folder", label: "Jinak" }))(first);
    expect(nodeWorkflowOf(second, "uzel").actions.map((a) => a.label)).toEqual(["Zkušební postup"]);
  });

  it("položka info nezmění stav", () => {
    const state = emptyDesktopState();
    expect(insertRulesFromItem("uzel", fixture({ kind: "info" }))(state)).toBe(state);
    expect(insertActionFromItem("uzel", fixture({ kind: "info" }))(state)).toBe(state);
  });
});
