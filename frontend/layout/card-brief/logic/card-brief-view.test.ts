import { describe, expect, it } from "vitest";
import {
  SPACE_PREVIEW,
  UNNAMED,
  briefJson,
  briefSummary,
  firstLine,
  handoffLink,
  kindLabel,
  phaseLabel,
  truncate,
} from "./card-brief-view";

const brief = {
  schema: "opora.node-brief/1",
  node: { id: "n-1", name: "4 Záložka Agenti", kind: "node" },
  goal: { goal: "Ukázat, co agent dostane.", nonGoals: "", acceptance: "" },
  definitionOfDone: {
    criteria: [
      { id: "c-1", text: "Panel ukazuje harness", checked: true },
      { id: "c-2", text: "Kopírování funguje", checked: false },
    ],
  },
  harness: {
    phase: "build",
    actions: [{ index: 0, id: "a-1", pipelineId: "ui.panel", label: "Postavit panel", params: { cesta: "frontend", model: "opus" } }],
    steps: [
      { id: "s-1", text: "Načíst balíček", assignee: "", done: true },
      { id: "s-2", text: "Složit sekce", assignee: "", done: false },
    ],
    stopConditions: ["Karta nemá podklad.", "   ", "Pravidlo must_not."],
  },
  graph: {
    incoming: [
      {
        edgeId: "e-1",
        from: "n-0",
        fromName: "3 Drop postupů",
        agentWorkspace: { frame: "f", handoff: "\n\n  Kam se podívat: fáze 3.  \nDruhá řádka." },
      },
    ],
    outgoing: [{ edgeId: "e-2", to: "n-2", toName: "", agentWorkspace: { handoff: "" } }],
    children: [{ id: "n-3" }, { id: "n-4" }],
    parent: { id: "s-9", name: "Sektor navbaru", agentWorkspace: { frame: "", handoff: "Bloky 1–6 sektoru." } },
  },
  loop: {
    done: { confirmed: true, at: "", by: "human", note: "Ověřeno člověkem" },
    openBlocks: 3,
    lastReport: { summary: "Panel stojí.", handoff: "Pokračuj fází 5." },
  },
  agentWorkspace: { frame: "Rámec karty.", handoff: "Předávka karty." },
};

describe("card-brief-view – první řádka a ořez", () => {
  it("bere první neprázdnou řádku a odřízne mezery", () => {
    expect(firstLine("\n\n  první  \ndruhá")).toBe("první");
    expect(firstLine("")).toBe("");
    expect(firstLine(null)).toBe("");
    expect(firstLine(42)).toBe("");
  });

  it("ořez přidá výpustku až za limitem, kratší text nechá být", () => {
    expect(truncate("krátké")).toBe("krátké");
    expect(truncate("abcdef", 3)).toBe("abc…");
    expect(truncate("x".repeat(SPACE_PREVIEW + 5))).toHaveLength(SPACE_PREVIEW + 1);
    expect(truncate(undefined)).toBe("");
  });

  it("fáze a druh karty mají české jméno, neznámé si nechá své id", () => {
    expect(phaseLabel("build")).toBe("Build");
    expect(phaseLabel("cizi")).toBe("cizi");
    expect(kindLabel("sector")).toBe("sektor");
    expect(kindLabel("cizi")).toBe("cizi");
  });
});

describe("card-brief-view – pohled na balíček", () => {
  const view = briefSummary(brief);

  it("hlavička nese jméno, druh, fázi a stav hotovo", () => {
    expect(view.header).toEqual({
      name: "4 Záložka Agenti",
      kind: "node",
      kindLabel: "uzel",
      phase: "build",
      phaseLabel: "Build",
      done: true,
      doneNote: "Ověřeno člověkem",
    });
  });

  it("cíl, kritéria a stop podmínky; prázdná podmínka se zahodí", () => {
    expect(view.goal.goal).toBe("Ukázat, co agent dostane.");
    expect(view.goal.criteria).toEqual([
      { id: "c-1", text: "Panel ukazuje harness", checked: true },
      { id: "c-2", text: "Kopírování funguje", checked: false },
    ]);
    expect(view.goal.stopConditions).toEqual(["Karta nemá podklad.", "Pravidlo must_not."]);
  });

  it("akce nesou popisek, pipeline a parametry jako dvojice klíč–hodnota", () => {
    expect(view.harness.actions).toEqual([
      {
        id: "a-1",
        label: "Postavit panel",
        pipelineId: "ui.panel",
        params: [
          { key: "cesta", value: "frontend" },
          { key: "model", value: "opus" },
        ],
      },
    ]);
    expect(view.harness.steps).toEqual([
      { id: "s-1", text: "Načíst balíček", done: true },
      { id: "s-2", text: "Složit sekce", done: false },
    ]);
  });

  it("smyčka nese otevřené bloky a souhrn poslední zprávy", () => {
    expect(view.loop).toEqual({ openBlocks: 3, lastReport: "Panel stojí." });
  });

  it("předávky: jména sousedů, první řádka jejich handoffu, rodič a počet dětí", () => {
    expect(view.handoffs.incoming).toEqual([{ id: "n-0", name: "3 Drop postupů", handoff: "Kam se podívat: fáze 3." }]);
    // Soused bez jména se pozná podle id, ne podle prázdného místa.
    expect(view.handoffs.outgoing).toEqual([{ id: "n-2", name: "n-2", handoff: "" }]);
    expect(view.handoffs.parent).toEqual({ id: "s-9", name: "Sektor navbaru", handoff: "Bloky 1–6 sektoru." });
    expect(view.handoffs.children).toBe(2);
  });

  it("pracovní prostor karty se ukáže zkrácený", () => {
    expect(view.workspace).toEqual({ frame: "Rámec karty.", handoff: "Předávka karty." });
    const long = briefSummary({ agentWorkspace: { frame: "a".repeat(SPACE_PREVIEW + 10), handoff: "" } });
    expect(long.workspace.frame.endsWith("…")).toBe(true);
    expect(long.workspace.frame).toHaveLength(SPACE_PREVIEW + 1);
  });

  it("souhrn spadne na handoff, když zpráva nemá summary", () => {
    const view2 = briefSummary({ loop: { lastReport: { summary: "", handoff: "Pokračuj fází 5." } } });
    expect(view2.loop.lastReport).toBe("Pokračuj fází 5.");
  });
});

describe("card-brief-view – prázdný a rozbitý balíček", () => {
  it("prázdný objekt dá prázdný, ale platný pohled", () => {
    const view = briefSummary({});
    expect(view.header).toEqual({
      name: UNNAMED,
      kind: "",
      kindLabel: "",
      phase: "",
      phaseLabel: "",
      done: false,
      doneNote: "",
    });
    expect(view.goal).toEqual({ goal: "", criteria: [], stopConditions: [] });
    expect(view.harness).toEqual({ actions: [], steps: [] });
    expect(view.loop).toEqual({ openBlocks: 0, lastReport: "" });
    expect(view.handoffs).toEqual({ incoming: [], outgoing: [], parent: null, children: 0 });
    expect(view.workspace).toEqual({ frame: "", handoff: "" });
  });

  it("null, pole i cizí typy uvnitř balíčku projdou bez výjimky", () => {
    expect(() => briefSummary(null)).not.toThrow();
    expect(() => briefSummary("balíček")).not.toThrow();
    const view = briefSummary({
      node: null,
      harness: { phase: 7, actions: "ne", steps: null, stopConditions: { a: 1 } },
      definitionOfDone: { criteria: [null, 3] },
      graph: { incoming: null, outgoing: undefined, parent: { name: "bez id" }, children: "ne" },
      loop: { done: null, openBlocks: "tři", lastReport: null },
      agentWorkspace: null,
    });
    expect(view.header.phase).toBe("");
    expect(view.goal.criteria).toEqual([
      { id: "", text: "", checked: false },
      { id: "", text: "", checked: false },
    ]);
    expect(view.handoffs.parent).toBeNull();
    expect(view.loop.openBlocks).toBe(0);
  });
});

describe("card-brief-view – co se kopíruje", () => {
  it("odkaz míří na předávku karty", () => {
    expect(handoffLink("n-1")).toBe("opora://agent-workspace/n-1#handoff");
  });

  it("zadání pro agenta je celý balíček, odsazený dvěma mezerami", () => {
    const json = briefJson({ schema: "opora.node-brief/1" });
    expect(json).toBe('{\n  "schema": "opora.node-brief/1"\n}');
    expect(briefJson(null)).toBe("null");
  });
});
