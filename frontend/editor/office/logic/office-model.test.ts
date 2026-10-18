import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { emptyDesktopState, nodeWorkflowOf, type DesktopState } from "@/shared/desktop-state/logic/types";
import type { WorkRow } from "@/editor/canvas/node-card/logic/use-work-overview";
import type { AssistantSession } from "@/layout/assistant-panel/logic/assistant-api";
import { buildOffice } from "./office-model";

const node = (id: string, kind: CanvasNode["kind"], parentId: string | null, x: number, y: number, extra: Partial<CanvasNode> = {}): CanvasNode =>
  ({ id, kind, parentId, name: id.toUpperCase(), purpose: "účel " + id, x, y, ...extra });

const session = (id: string, state: AssistantSession["state"], extra: Partial<AssistantSession> = {}): AssistantSession => ({
  id, projectId: "p", workspace: "main", title: "Relace " + id, model: "sonnet", claudeSessionId: null,
  createdAt: "2026-10-17T10:00:00Z", updatedAt: "2026-10-17T10:00:00Z", state, nodeId: null, sectorId: null, lastSeq: 0, ...extra,
});

const row = (id: string, status: WorkRow["status"], agent = ""): WorkRow =>
  ({ id, name: id, status, agent, startedAt: null, lastActivity: null, touched: null, waitingOnHuman: [], blockedBy: [] });

function fixture(): { graph: Graph; state: DesktopState } {
  const graph: Graph = {
    nodes: [
      node("a1", "area", null, 0, 0, { size: { w: 1000, h: 1000 }, color: "teal" }),
      node("a2", "area", null, 0, 2000, { size: { w: 1000, h: 1000 } }),
      node("s1", "sector", null, 100, 100),
      node("s2", "sector", null, 5000, 5000),
      node("c1", "node", "s1", 0, 0),
      node("c2", "node", "s1", 0, 400),
      node("c3", "node", "s2", 0, 0),
      node("loose", "node", null, 4000, 4000),
    ],
    edges: [],
  };
  const state = emptyDesktopState();
  state.nodes.c2 = { ...nodeWorkflowOf(state, "c2"), done: { confirmed: true, at: "", by: "human", note: "" } };
  return { graph, state };
}

describe("buildOffice – oddělení, místnosti, stoly", () => {
  it("sektor uvnitř oblasti je místnost oddělení, sektor mimo oblast je v Hale", () => {
    const office = buildOffice({ ...fixture(), sessions: [] });
    expect(office.departments.map((d) => [d.id, d.color, d.rooms.map((r) => r.id)])).toEqual([["a1", "teal", ["s1"]], ["a2", "indigo", []]]);
    expect(office.hall.map((r) => r.id)).toEqual(["s2"]);
  });

  it("stoly jsou karty sektoru se stavovou větou a pruh počítá tóny", () => {
    const office = buildOffice({ ...fixture(), sessions: [], workRows: { c1: row("c1", "claimed", "Ada") } });
    const room = office.departments[0].rooms[0];
    expect(room.desks.map((d) => [d.id, d.closed, d.state.tone, d.state.text])).toEqual([
      ["c1", false, "run", "Pracuje Ada"],
      ["c2", true, "ok", "Uzavřeno"],
    ]);
    expect(room.tones).toEqual({ ok: 1, run: 1, warn: 0, fail: 0, idle: 0 });
  });
});

describe("buildOffice – kdo kde sedí", () => {
  it("relace s kartou sedí u stolu, se sektorem u společného stolu, bez vazby v Recepci; zavřené se nekreslí", () => {
    const office = buildOffice({
      ...fixture(),
      sessions: [
        session("desk", "running", { nodeId: "c1" }),
        session("common", "idle", { sectorId: "s2" }),
        session("main", "idle"),
        session("gone", "closed", { nodeId: "c1" }),
      ],
    });
    expect(office.departments[0].rooms[0].desks[0].workers.map((w) => w.id)).toEqual(["desk"]);
    expect(office.hall[0].common.map((w) => w.id)).toEqual(["common"]);
    expect(office.reception.map((w) => w.id)).toEqual(["main"]);
  });

  it("vazba mimo budovu (neznámá karta nebo sektor, karta mimo sektor) skončí v Recepci", () => {
    const office = buildOffice({
      ...fixture(),
      sessions: [session("x", "idle", { nodeId: "missing" }), session("y", "idle", { sectorId: "nope" }), session("z", "idle", { nodeId: "loose" })],
    });
    expect(office.reception.map((w) => w.id)).toEqual(["x", "y", "z"]);
  });

  it("relace s kartou i sektorem sedí u stolu karty", () => {
    const office = buildOffice({ ...fixture(), sessions: [session("both", "idle", { nodeId: "c3", sectorId: "s2" })] });
    expect(office.hall[0].desks[0].workers.map((w) => w.id)).toEqual(["both"]);
    expect(office.hall[0].common).toEqual([]);
  });

  it("čekající jsou jen waiting_approval, nejstarší první, při shodě v pořadí seznamu", () => {
    const office = buildOffice({
      ...fixture(),
      sessions: [
        session("new", "waiting_approval", { updatedAt: "2026-10-17T12:00:00Z" }),
        session("run", "running"),
        session("old", "waiting_approval", { updatedAt: "2026-10-17T09:00:00Z" }),
        session("tie", "waiting_approval", { updatedAt: "2026-10-17T12:00:00Z" }),
      ],
    });
    expect(office.waiting.map((w) => w.id)).toEqual(["old", "new", "tie"]);
  });
});
