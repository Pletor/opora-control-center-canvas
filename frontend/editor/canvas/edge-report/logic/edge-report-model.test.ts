import { describe, expect, it } from "vitest";
import { edgeReportView, edgeRoute, emptyReport, filledFields, formatSent, reportOf, reportSignature, setEdgeReport } from "./edge-report-model";
import { emptyDesktopState, MAX_REPORT_FIELD, type Block } from "@/shared/desktop-state/logic/types";
import { emptyBranch, emptyNodeWorkflow } from "@/shared/desktop-state/logic/types";
import type { GraphEdge } from "@/shared/types/logic/types";

const block = (extra: Partial<Block>): Block => ({
  id: "b1", number: "2", title: "Návrh API", text: "", tags: [], todos: [], images: [], parentBlockId: "",
  state: { status: "open", condition: "", onMet: emptyBranch(), onUnmet: emptyBranch() }, ...extra,
});

describe("edge-report-model", () => {
  it("prázdná zpráva má všech pět polí, podpis člověka a žádné razítko", () => {
    const report = emptyReport();
    expect(filledFields(report)).toBe(0);
    expect(report.by).toBe("human");
    expect(reportSignature(report)).toBe("");
    expect(reportOf(emptyDesktopState(), "e1")).toEqual(report);
  });

  it("zápis doplní jen poslané pole, orazítkuje čas a podepíše člověka", () => {
    const first = setEdgeReport("e1", { log: "Přepsal jsem router." })(emptyDesktopState());
    const report = reportOf(first, "e1");
    expect(report.log).toBe("Přepsal jsem router.");
    expect(report.summary).toBe("");
    expect(report.by).toBe("human");
    expect(report.updatedAt).not.toBe("");
    const second = setEdgeReport("e1", { summary: "Hotovo." })(first);
    expect(reportOf(second, "e1")).toMatchObject({ log: "Přepsal jsem router.", summary: "Hotovo." });
    expect(filledFields(reportOf(second, "e1"))).toBe(2);
  });

  it("zápis agenta si nechá svůj podpis a dlouhý text se ořízne na 4000 znaků", () => {
    const state = setEdgeReport("e1", { by: "agent", agent: "builder", updatedAt: "2026-09-14T10:00:00Z", errors: "x".repeat(5000) })(emptyDesktopState());
    const report = reportOf(state, "e1");
    expect(report.by).toBe("agent");
    expect(report.errors).toHaveLength(MAX_REPORT_FIELD);
    expect(reportSignature(report)).toBe("agent builder · 2026-09-14T10:00:00Z");
  });

  it("zprávy se nepřepisují napříč vazbami", () => {
    let state = setEdgeReport("e1", { log: "první" })(emptyDesktopState());
    state = setEdgeReport("e2", { log: "druhá" })(state);
    expect(reportOf(state, "e1").log).toBe("první");
    expect(reportOf(state, "e2").log).toBe("druhá");
  });

  it("hlava panelu pojmenuje uzly, port a u vazby z bloku i číslo bloku a tlačítko", () => {
    const nodes = [{ id: "a", name: "Přihlášení" }, { id: "b", name: "Profil" }];
    const workflow = { ...emptyNodeWorkflow(), blocks: [block({ ports: [{ id: "p1", label: "Schváleno" }] })] };
    const blockEdge: GraphEdge = { id: "e1", source: "a", target: "b", port: "block", sourceBlockId: "b1", sourcePortId: "p1" };
    expect(edgeReportView(blockEdge, nodes, workflow)).toEqual({
      edgeId: "e1", sourceName: "Přihlášení", targetName: "Profil", portLabel: "PORT BLOKU",
      blockNumber: "2", blockTitle: "Návrh API", portName: "Schváleno",
    });
    const plain: GraphEdge = { id: "e2", source: "a", target: "b" };
    expect(edgeReportView(plain, nodes, workflow)).toMatchObject({ portLabel: "DALŠÍ KROK", blockNumber: "", portName: "" });
  });
});

describe("edge-report-model: Sent a Date", () => {
  it("změna neprázdného předání nastaví sentAt na čas zápisu", () => {
    const state = setEdgeReport("e1", { handoff: "Pokračuj v routeru.", updatedAt: "2026-10-02T08:00:00Z" })(emptyDesktopState());
    expect(reportOf(state, "e1").sentAt).toBe("2026-10-02T08:00:00Z");
    // Stejný text ani prázdné předání čas nemění.
    const same = setEdgeReport("e1", { handoff: "Pokračuj v routeru.", updatedAt: "2026-10-03T08:00:00Z" })(state);
    expect(reportOf(same, "e1").sentAt).toBe("2026-10-02T08:00:00Z");
    const cleared = setEdgeReport("e1", { handoff: "  ", updatedAt: "2026-10-04T08:00:00Z" })(state);
    expect(reportOf(cleared, "e1").sentAt).toBe("2026-10-02T08:00:00Z");
  });

  it("sentAt ani due se neztratí při přepisu jiných polí", () => {
    let state = setEdgeReport("e1", { handoff: "A", updatedAt: "2026-10-02T08:00:00Z" })(emptyDesktopState());
    state = setEdgeReport("e1", { due: "2026-10-10" })(state);
    state = setEdgeReport("e1", { summary: "Souhrn" })(state);
    state = setEdgeReport("e1", { log: "Log" })(state);
    expect(reportOf(state, "e1")).toMatchObject({ handoff: "A", summary: "Souhrn", log: "Log", sentAt: "2026-10-02T08:00:00Z", due: "2026-10-10" });
  });

  it("starší zpráva bez nových polí zůstane bez nich", () => {
    const state = setEdgeReport("e1", { log: "x" })(emptyDesktopState());
    expect("sentAt" in reportOf(state, "e1")).toBe(false);
    expect("due" in reportOf(state, "e1")).toBe(false);
  });

  it("trasa nese názvy a adresy obou karet", () => {
    const nodes = [
      { id: "s", name: "Editor", parentId: null },
      { id: "a", name: "[task] Pop-up tvorby", parentId: "s" },
      { id: "b", name: "Profil", parentId: null },
    ];
    expect(edgeRoute({ source: "a", target: "b" }, nodes)).toEqual({
      from: { name: "[task] Pop-up tvorby", address: "editor/pop-up-tvorby" },
      to: { name: "Profil", address: "profil" },
    });
    expect(edgeRoute({ source: "x", target: "b" }, nodes).from).toEqual({ name: "x", address: "" });
  });

  it("čas předání se formátuje, chybějící je nepředáno", () => {
    expect(formatSent(undefined)).toBe("nepředáno");
    expect(formatSent("")).toBe("nepředáno");
    expect(formatSent("2026-10-02T08:05:00")).toBe("2. 10. 2026 08:05");
    expect(formatSent("není čas")).toBe("není čas");
  });
});
