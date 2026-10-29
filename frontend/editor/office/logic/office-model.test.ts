import { describe, expect, it } from "vitest";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { emptyDesktopState, nodeWorkflowOf, type DesktopState } from "@/shared/desktop-state/logic/types";
import type { WorkRow } from "@/editor/canvas/node-card/logic/use-work-overview";
import { buildOffice, workerCount, type OfficeTask } from "./office-model";

const node = (id: string, kind: CanvasNode["kind"], parentId: string | null, x: number, y: number, extra: Partial<CanvasNode> = {}): CanvasNode =>
  ({ id, kind, parentId, name: id.toUpperCase(), purpose: "účel " + id, x, y, ...extra });

const task = (taskId: string, status: string, sessionId: string | null, nodeId: string | null): OfficeTask =>
  ({ taskId, title: "Úkol " + taskId, status, sessionId, nodeId, updatedAt: "2026-10-29T10:00:00Z" });

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
    const office = buildOffice({ ...fixture(), tasks: [] });
    expect(office.departments.map((d) => [d.id, d.color, d.rooms.map((r) => r.id)])).toEqual([["a1", "teal", ["s1"]], ["a2", "indigo", []]]);
    expect(office.hall.map((r) => r.id)).toEqual(["s2"]);
  });

  it("stoly jsou karty sektoru se stavovou větou a pruh počítá tóny", () => {
    const office = buildOffice({ ...fixture(), tasks: [], workRows: { c1: row("c1", "claimed", "Ada") } });
    const room = office.departments[0].rooms[0];
    expect(room.desks.map((d) => [d.id, d.closed, d.state.tone, d.state.text])).toEqual([
      ["c1", false, "run", "Pracuje Ada"],
      ["c2", true, "ok", "Uzavřeno"],
    ]);
    expect(room.tones).toEqual({ ok: 1, run: 1, warn: 0, fail: 0, idle: 0 });
  });
});

describe("buildOffice – kdo kde sedí", () => {
  it("relace s úkolem na kartě sedí u stolu, na sektoru u společného stolu, bez uzlu v Recepci", () => {
    const office = buildOffice({
      ...fixture(),
      tasks: [
        task("t1", "assigned", "desk", "c1"),
        task("t2", "assigned", "common", "s2"),
        task("t3", "assigned", "main", null),
      ],
    });
    expect(office.departments[0].rooms[0].desks[0].workers.map((w) => [w.id, w.taskId])).toEqual([["desk", "t1"]]);
    expect(office.hall[0].common.map((w) => w.id)).toEqual(["common"]);
    expect(office.reception.map((w) => w.id)).toEqual(["main"]);
    expect(workerCount(office)).toBe(3);
  });

  it("pracovník je jen přidělený úkol s relací; ready, hotové a zrušené se nekreslí", () => {
    const office = buildOffice({
      ...fixture(),
      tasks: [task("a", "ready", null, "c1"), task("b", "done", "s-done", "c1"), task("c", "cancelled", "s-x", "c1"), task("d", "assigned", null, "c1")],
    });
    expect(office.departments[0].rooms[0].desks[0].workers).toEqual([]);
    expect(office.reception).toEqual([]);
  });

  it("relace se dvěma úkoly sedí jen jednou, u prvního", () => {
    const office = buildOffice({ ...fixture(), tasks: [task("t1", "assigned", "s", "c1"), task("t2", "assigned", "s", "c3")] });
    expect(office.departments[0].rooms[0].desks[0].workers.map((w) => w.taskId)).toEqual(["t1"]);
    expect(office.hall[0].desks[0].workers).toEqual([]);
  });

  it("uzel mimo budovu (neznámý nebo karta mimo sektor) skončí v Recepci", () => {
    const office = buildOffice({ ...fixture(), tasks: [task("x", "assigned", "x", "missing"), task("z", "assigned", "z", "loose")] });
    expect(office.reception.map((w) => w.id)).toEqual(["x", "z"]);
  });
});
