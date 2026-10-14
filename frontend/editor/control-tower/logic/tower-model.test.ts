import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { emptyDesktopState, type DesktopState } from "@/shared/desktop-state/logic/types";
import type { WorkOverview, WorkRow } from "@/editor/canvas/node-card/logic/use-work-overview";
import type { PipelineStage } from "@/editor/workflow/card-pipeline/logic/pipeline-model";
import {
  INBOX_LIMIT, buildTower, contentLabel, countSegments, emptyCounts, groupInbox, inboxCardCount, inboxKinds, inboxPage, looseArea, towerFrom, towerStructure,
} from "./tower-model";

const node = (id: string, kind: CanvasNode["kind"], parentId: string | null, x: number, y: number, extra: Partial<CanvasNode> = {}): CanvasNode =>
  ({ id, kind, parentId, name: id.toUpperCase(), purpose: "účel " + id, x, y, ...extra });

const stage = (id: string, status: PipelineStage["status"]): PipelineStage =>
  ({ id, kind: "critic", lens: "hacker", title: "Kritik " + id, brief: "", status, note: "díra v API", by: "agent", approved: true, doneBy: "", at: "" });

const row = (id: string, status: WorkRow["status"], asks: string[] = []): WorkRow =>
  ({ id, name: id, status, agent: "", startedAt: null, lastActivity: null, touched: null, waitingOnHuman: asks.map((ask, i) => ({ blockId: "b" + i, ask })), blockedBy: [] });

function fixture(): { graph: Graph; state: DesktopState; work: WorkOverview } {
  const graph: Graph = {
    nodes: [
      node("a2", "area", null, 0, 2000, { size: { w: 1000, h: 1000 }, color: "teal" }),
      node("a1", "area", null, 0, 0, { size: { w: 1000, h: 1000 } }),
      node("s2", "sector", null, 100, 500),
      node("s1", "sector", null, 100, 100),
      node("s3", "sector", null, 100, 2100),
      node("ss1", "sector", "s1", 0, 0),
      node("c1", "node", "s1", 0, 0),
      node("c2", "node", "s1", 0, 400),
      node("c3", "node", "s1", 400, 0),
      node("c4", "node", "ss1", 0, 0),
      node("c5", "node", "s2", 0, 0),
      node("c6", "node", "s3", 0, 0, { card: { layer: "frontend" } }),
      node("c7", "node", null, 500, 2500),
      node("l1", "node", null, 5000, 5000),
    ],
    edges: [],
  };
  const state = emptyDesktopState();
  state.nodes = {
    c1: { phase: "build", criteria: [], steps: [], done: { confirmed: true, at: "", by: "human", note: "" } },
    c2: { phase: "build", criteria: [], steps: [], done: { confirmed: false, at: "", by: "agent", note: "" } },
    c5: { phase: "build", criteria: [], steps: [], stages: { profile: "code", items: [stage("x", "passed"), stage("y", "failed")] } },
    c6: { phase: "build", criteria: [], steps: [], ideas: [
      { id: "i1", text: "", by: "human", source: "human", at: "", status: "open" },
      { id: "i2", text: "", by: "human", source: "human", at: "", status: "done" },
    ] },
  };
  const work: WorkOverview = { nodes: { c3: row("c3", "claimed"), c4: row("c4", "waiting-human", ["Jaký formát?"]) }, sectors: {} };
  return { graph, state, work };
}

describe("buildTower – pyramida Velínu", () => {
  it("skládá oblasti podle polohy, sektory podle členství a podsektory podle rodiče", () => {
    const tower = buildTower(fixture());
    expect(tower.areas.map((a) => a.id)).toEqual(["a1", "a2"]);
    expect(tower.areas[0].sectors.map((s) => s.id)).toEqual(["s1", "s2"]);
    expect(tower.areas[0].color).toBe("indigo");
    expect(tower.areas[1].color).toBe("teal");
    expect(tower.areas[1].sectors.map((s) => s.id)).toEqual(["s3"]);
    expect(tower.areas[1].cards.map((c) => c.id)).toEqual(["c7"]);
    const s1 = tower.areas[0].sectors[0];
    expect(s1.cards.map((c) => c.id)).toEqual(["c1", "c3", "c2"]);
    expect(s1.subsectors.map((s) => s.id)).toEqual(["ss1"]);
    expect(s1.subsectors[0].cards.map((c) => c.id)).toEqual(["c4"]);
    expect(tower.loose).toEqual([]);
    expect(tower.looseCards.map((c) => c.id)).toEqual(["l1"]);
  });

  it("karta nese stav, uzavření, návrh, proces, otázky, podněty a vrstvu", () => {
    const tower = buildTower(fixture());
    const [s1, s2] = tower.areas[0].sectors;
    const [c1, c3, c2] = s1.cards;
    expect(c1).toMatchObject({ closed: true, status: "done", proposed: false });
    expect(c2).toMatchObject({ closed: false, proposed: true, status: "idle" });
    expect(c3.status).toBe("claimed");
    expect(s1.subsectors[0].cards[0].waiting).toEqual(["Jaký formát?"]);
    expect(s2.cards[0].process?.waitingOnHuman).toBe(true);
    const c6 = tower.areas[1].sectors[0].cards[0];
    expect(c6).toMatchObject({ ideas: 1, layer: "frontend" });
  });

  it("sčítá zdola nahoru bez překryvu košů", () => {
    const tower = buildTower(fixture());
    const s1 = tower.areas[0].sectors[0];
    expect(s1.counts).toEqual({ cards: 4, closed: 1, running: 1, waitingHuman: 1, proposed: 1, failed: 0, unrouted: 3 });
    expect(tower.areas[0].counts).toMatchObject({ cards: 5, failed: 1 });
    expect(tower.totals).toMatchObject({ cards: 8, closed: 1, running: 1, waitingHuman: 1, proposed: 1, failed: 1 });
    expect(tower.areas[0].sectors[1].verified).toBe(false);
    expect(tower.areas[0].sectors[1].gateName).toBe("Nenastavena");
    const segments = countSegments(tower.totals);
    expect(segments.map((s) => s.key)).toEqual(["closed", "proposed", "failed", "waitingHuman", "running", "idle"]);
    expect(segments.reduce((sum, s) => sum + s.count, 0)).toBe(8);
    expect(countSegments(emptyCounts())).toEqual([]);
  });

  it("fronta řadí ke schválení, uvízlé, otázky a nese oblast i sektor", () => {
    const tower = buildTower(fixture());
    expect(tower.inbox.map((i) => [i.kind, i.nodeId])).toEqual([["proposed", "c2"], ["stuck", "c5"], ["waiting", "c4"]]);
    expect(tower.inbox[1].text).toContain("Kritik y — díra v API");
    expect(tower.inbox[2]).toMatchObject({ sectorId: "ss1", sectorName: "SS1", areaId: "a1", areaName: "A1", text: "Jaký formát?" });
    expect(groupInbox(tower.inbox).map((g) => g.title)).toEqual(["A1 › S1", "A1 › S2", "A1 › SS1"]);
    expect(tower.workState).toBe("loaded");
  });

  it("fronta se stránkuje po 50, filtruje podle druhu a počítá dotčené karty", () => {
    const graph: Graph = { nodes: [node("s", "sector", null, 0, 0)], edges: [] };
    const state = emptyDesktopState();
    for (let i = 0; i < 70; i++) {
      graph.nodes.push(node("n" + i, "node", "s", i, 0));
      state.nodes["n" + i] = { phase: "build", criteria: [], steps: [], done: { confirmed: false, at: "", by: "agent", note: "" } };
    }
    const work: WorkOverview = { nodes: { n0: row("n0", "waiting-human", ["A?", "B?"]) }, sectors: {} };
    const tower = buildTower({ graph, state, work });
    expect(tower.inbox).toHaveLength(72);
    expect(inboxCardCount(tower.inbox)).toBe(70);
    expect(inboxKinds(tower.inbox)).toEqual({ all: 72, proposed: 70, stuck: 0, waiting: 2 });
    expect(inboxPage(tower.inbox, "all", INBOX_LIMIT)).toMatchObject({ total: 72, more: 22 });
    expect(inboxPage(tower.inbox, "all", INBOX_LIMIT).items).toHaveLength(50);
    expect(inboxPage(tower.inbox, "all", 2 * INBOX_LIMIT)).toMatchObject({ total: 72, more: 0 });
    expect(inboxPage(tower.inbox, "waiting", INBOX_LIMIT).items.map((i) => i.text)).toEqual(["A?", "B?"]);
    expect(tower.loose[0].counts.proposed).toBe(70);
    expect(looseArea(tower)?.counts.cards).toBe(70);
  });

  it("groupInbox skupí podle id, ne podle názvu", () => {
    const graph: Graph = {
      nodes: [
        node("a", "area", null, 0, 0, { name: "Stejná", size: { w: 1000, h: 1000 } }),
        node("b", "area", null, 0, 2000, { name: "Stejná", size: { w: 1000, h: 1000 } }),
        node("p", "node", null, 100, 100), node("q", "node", null, 100, 2100),
      ],
      edges: [],
    };
    const state = emptyDesktopState();
    for (const id of ["p", "q"]) state.nodes[id] = { phase: "build", criteria: [], steps: [], done: { confirmed: false, at: "", by: "agent", note: "" } };
    expect(groupInbox(buildTower({ graph, state }).inbox).map((g) => g.key)).toEqual(["area:a", "area:b"]);
  });

  it("bez přehledu práce jsou otevřené karty bez známého stavu a fronta nese jen to, co je ve stavu plátna", () => {
    const { graph, state } = fixture();
    const tower = buildTower({ graph, state, workState: "unavailable" });
    expect(tower.workState).toBe("unavailable");
    const s1 = tower.areas[0].sectors[0];
    expect(s1.cards.map((c) => c.status)).toEqual(["done", "idle", "idle"]);
    expect(s1.cards.map((c) => c.statusKnown)).toEqual([true, false, false]);
    expect(s1.subsectors[0].cards[0].waiting).toEqual([]);
    expect(tower.totals.running).toBe(0);
    expect(tower.inbox.map((i) => i.kind)).toEqual(["proposed", "stuck"]);
    expect(buildTower({ graph, state }).workState).toBe("unavailable");
    expect(towerFrom(towerStructure(graph), state, undefined, "loading").workState).toBe("loading");
  });

  it("součty jdou přes celou hloubku sektorů, i za hranicí zobrazení", () => {
    const nodes = [node("d1", "sector", null, 0, 0)];
    for (let i = 2; i <= 7; i++) nodes.push(node("d" + i, "sector", "d" + (i - 1), 0, 0));
    nodes.push(node("deep", "node", "d7", 0, 0));
    const tower = buildTower({ graph: { nodes, edges: [] }, state: emptyDesktopState() });
    expect(tower.loose[0].counts.cards).toBe(1);
    let cursor = tower.loose[0];
    for (let i = 2; i <= 7; i++) cursor = cursor.subsectors[0];
    expect(cursor.cards[0].id).toBe("deep");
  });

  it("osiřelé sektory a karty jdou do pásma Mimo oblast a cyklus nespadne", () => {
    const graph: Graph = {
      nodes: [
        node("ghostSector", "sector", "missing", 0, 0),
        node("ghostCard", "node", "ghostSector", 0, 0),
        node("lostCard", "node", "missing", 0, 100),
        node("cx", "sector", "cy", 0, 200), node("cy", "sector", "cx", 0, 300),
        node("cycleCard", "node", "cy", 0, 0),
      ],
      edges: [],
    };
    const tower = buildTower({ graph, state: emptyDesktopState() });
    expect(tower.loose.map((s) => s.id)).toEqual(["ghostSector", "cx"]);
    expect(tower.loose[0].cards.map((c) => c.id)).toEqual(["ghostCard"]);
    expect(tower.loose[1].subsectors.map((s) => s.id)).toEqual(["cy"]);
    expect(tower.looseCards.map((c) => c.id)).toEqual(["lostCard"]);
    expect(tower.totals.cards).toBe(3);
  });

  it("prázdné plátno nespadne a popisek obsahu uvádí jen nenulové části", () => {
    expect(buildTower({ graph: { nodes: [], edges: [] }, state: emptyDesktopState() })).toMatchObject({ areas: [], loose: [], looseCards: [], inbox: [] });
    expect(looseArea(buildTower({ graph: { nodes: [], edges: [] }, state: emptyDesktopState() }))).toBeNull();
    expect(contentLabel(3, 1)).toBe("Obsah: 3 karty · 1 podsektor");
    expect(contentLabel(5, 0)).toBe("Obsah: 5 karet");
    expect(contentLabel(0, 2)).toBe("Obsah: 2 podsektory");
    expect(contentLabel(0, 0)).toBe("Obsah: prázdný");
  });
});
