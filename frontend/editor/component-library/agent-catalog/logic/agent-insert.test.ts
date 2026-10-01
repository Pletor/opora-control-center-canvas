import { describe, expect, it } from "vitest";
import { emptyDesktopState, nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import {
  actionFromItem,
  insertActionFromItem,
  insertRulesFromItem,
  NEW_CARD_PHASE,
  PHASE_LABELS,
  phaseNote,
  phasesFromTemplate,
  ruleFromItem,
  sectorFromWorkflow,
} from "./agent-insert";
import { agentItemById, type AgentItem } from "./agent-catalog";

/** Zkušební položka: základ, ke kterému se v testu dopisuje jen to, co se zkouší. */
const fixture = (patch: Partial<AgentItem> = {}): AgentItem => ({
  id: "fixture",
  category: "rules",
  label: "Zkušební postup",
  hint: "Jen pro test",
  icon: "×",
  kind: "rule",
  rules: { must: ["Musí platit A", "Musí platit B"], mustNot: ["Nesmí C"] },
  decomposition: [
    { title: "discover", text: "Najdi podklady." },
    { title: "define", text: "Popiš rozhraní." },
  ],
  template: [
    "1. discover — najdi podklady.",
    "2. define — popiš rozhraní.",
    "3. build — postav to.",
    "4. verify — ověř to.",
    "5. live — předej to.",
  ].join("\n"),
  endCriteria: "Hotovo, když projdou testy.",
  stopCondition: "Chybí podklad — zastav a vyžádej si ho.",
  refs: ["fe-pure-model", "css-bem-block"],
  ...patch,
});

describe("agent-insert – pravidla uzlu z položky", () => {
  it("musí a nesmí se stanou pravidly uzlu s popiskem položky vepředu", () => {
    const rules = ruleFromItem(fixture())!;
    expect(rules.map((r) => [r.kind, r.text])).toEqual([
      ["must", "Zkušební postup: Musí platit A"],
      ["must", "Zkušební postup: Musí platit B"],
      ["must_not", "Zkušební postup: Nesmí C"],
    ]);
    expect(new Set(rules.map((r) => r.id)).size).toBe(3);
  });

  it("agent dostane navíc první pravidlo s rolí a modelem", () => {
    const rules = ruleFromItem(fixture({ kind: "agent", label: "Subagent Explore: haiku", hint: "role: hledání · model: haiku" }))!;
    expect(rules[0]).toMatchObject({
      kind: "must",
      text: "Role: Subagent Explore: haiku. role: hledání · model: haiku",
    });
    expect(rules.length).toBe(4);
  });

  it("položka info se netáhne: null ze všech tří překladů", () => {
    const info = fixture({ kind: "info" });
    expect(ruleFromItem(info)).toBeNull();
    expect(actionFromItem(info)).toBeNull();
    expect(sectorFromWorkflow(info, null, 0, 0)).toBeNull();
  });
});

describe("agent-insert – akce z položky", () => {
  it("pipeline si drží identitu položky a kroky nese jako text v parametrech", () => {
    const action = actionFromItem(fixture({ kind: "action", id: "pl-feature-folder" }))!;
    expect(action.pipelineId).toBe("pl-feature-folder");
    expect(action.label).toBe("Zkušební postup");
    expect(action.params).toEqual({
      steps: "discover → define",
      endCriteria: "Hotovo, když projdou testy.",
      stopCondition: "Chybí podklad — zastav a vyžádej si ho.",
      refs: "fe-pure-model, css-bem-block",
    });
  });

  it("parametry jsou objekt textů v mezích backendu (ACTION_KEYS, MAX_PARAMS)", () => {
    const action = actionFromItem(agentItemById("pl-verify-before-done")!)!;
    expect(Object.keys(action.params).length).toBeLessThanOrEqual(50);
    expect(Object.values(action.params).every((value) => typeof value === "string")).toBe(true);
    expect(action.id).not.toBe(actionFromItem(fixture())!.id);
  });
});

describe("agent-insert – sektor z workflow", () => {
  const insert = () => sectorFromWorkflow(fixture({ kind: "workflow" }), "vrstva", 120.4, 40.6)!;

  it("sektor je rám postupu na místě puštění", () => {
    const { sector } = insert();
    expect(sector.kind).toBe("sector");
    expect(sector.parentId).toBe("vrstva");
    expect(sector.name).toBe("Zkušební postup");
    expect(sector.purpose).toBe("Jen pro test");
    expect({ x: sector.x, y: sector.y }).toEqual({ x: 120, y: 41 });
  });

  it("každá fáze šablony má uvnitř sektoru vlastní kartu v jedné řadě", () => {
    const { sector, children, phases } = insert();
    expect(phases).toEqual(["discover", "define", "build", "verify", "live"]);
    expect(children.map((c) => c.name)).toEqual(["Objevit", "Definovat", "Postavit", "Ověřit", "Provoz"]);
    expect(children.every((c) => c.parentId === sector.id && c.kind === "node")).toBe(true);
    expect(children.map((c) => [c.x, c.y])).toEqual([
      [80, 80],
      [400, 80],
      [720, 80],
      [1040, 80],
      [1360, 80],
    ]);
    // Podstata karty je krok rozpadu se stejným názvem, jinak řádek šablony bez čísla.
    expect(children[0].purpose).toBe("Najdi podklady.");
    expect(children[2].purpose).toBe("build — postav to.");
  });

  it("sousední fáze spojuje vazba next, poslední už nikam nepokračuje", () => {
    const { children, edges } = insert();
    expect(edges.map((e) => [e.source, e.target, e.port])).toEqual([
      [children[0].id, children[1].id, "next"],
      [children[1].id, children[2].id, "next"],
      [children[2].id, children[3].id, "next"],
      [children[3].id, children[4].id, "next"],
    ]);
    expect(new Set(edges.map((e) => e.id)).size).toBe(4);
  });

  it("stav nových karet nese fázi, kterou karta zastupuje, a kritérium konce visí na poslední", () => {
    const { children, nodes } = insert();
    expect(Object.keys(nodes).sort()).toEqual(children.map((c) => c.id).sort());
    // Vznik karty v libovolné fázi backend nehlídá; kritérii hlídá jen postup existující karty.
    expect(children.map((c) => nodes[c.id].phase)).toEqual(["discover", "define", "build", "verify", "live"]);
    expect(NEW_CARD_PHASE).toBe("discover");
    expect(nodes[children[0].id].criteria).toEqual([]);
    expect(nodes[children[4].id].criteria.map((c) => [c.text, c.checked])).toEqual([
      ["Hotovo, když projdou testy.", false],
    ]);
  });

  it("fáze se čtou ze šablony; co v ní není, kartu nedostane", () => {
    expect(phasesFromTemplate("1. discover\n2. build\n3. live")).toEqual(["discover", "build", "live"]);
    expect(phasesFromTemplate("bez fází")).toEqual([]);
    expect(sectorFromWorkflow(fixture({ kind: "workflow", template: "bez fází" }), null, 0, 0)).toBeNull();
    expect(phaseNote(fixture(), "verify")).toBe("verify — ověř to.");
    expect(PHASE_LABELS.live).toBe("Provoz");
  });

  it("vydané workflow „Zadání → hotovo v pěti fázích“ dá sektor s pěti kartami", () => {
    const item = agentItemById("wf-five-phases")!;
    const made = sectorFromWorkflow(item, null, 0, 0)!;
    expect(made.children.length).toBe(5);
    expect(made.edges.length).toBe(4);
    expect(made.children[4].purpose).toBe(item.decomposition[4].text);
  });
});

describe("agent-insert – vložení do vybrané karty", () => {
  it("pravidla se přidají jednou; druhé puštění téže dlaždice kartu nezaplevelí", () => {
    const item = fixture();
    const first = insertRulesFromItem("uzel", item)(emptyDesktopState());
    const second = insertRulesFromItem("uzel", item)(first);
    expect(nodeWorkflowOf(second, "uzel").rules.length).toBe(3);
    // Jiná položka se přidá vedle, protože má jiný text.
    const third = insertRulesFromItem("uzel", fixture({ label: "Jiný postup" }))(second);
    expect(nodeWorkflowOf(third, "uzel").rules.length).toBe(6);
    expect(nodeWorkflowOf(third, "jiny").rules).toEqual([]);
  });

  it("akce se pozná podle pipelineId, takže se linka nerozdvojí ani po přejmenování", () => {
    const item = fixture({ kind: "action", id: "pl-feature-folder" });
    const first = insertActionFromItem("uzel", item)(emptyDesktopState());
    const second = insertActionFromItem("uzel", fixture({ kind: "action", id: "pl-feature-folder", label: "Jinak" }))(first);
    expect(nodeWorkflowOf(second, "uzel").actions.map((a) => a.label)).toEqual(["Zkušební postup"]);
    const third = insertActionFromItem("uzel", fixture({ kind: "action", id: "pl-verify-before-done" }))(second);
    expect(nodeWorkflowOf(third, "uzel").actions.map((a) => a.pipelineId)).toEqual([
      "pl-feature-folder",
      "pl-verify-before-done",
    ]);
  });

  it("položka info nezmění stav ani jedním vložením", () => {
    const info = fixture({ kind: "info" });
    const state = emptyDesktopState();
    expect(insertRulesFromItem("uzel", info)(state)).toBe(state);
    expect(insertActionFromItem("uzel", info)(state)).toBe(state);
  });
});
