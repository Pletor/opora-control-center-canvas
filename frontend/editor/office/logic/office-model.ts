// Kancelář (docs/kancelar.md §1–2): z grafu, ticketů práce, přehledu práce a pronájmů složí budovu.
// Oddělení = oblast na kořenové vrstvě, místnost = sektor (člen oblasti podle polohy, jinak Hala),
// stůl = karta s `parentId` = sektor, pracovník = relace brány, která drží ticket (claimed / in_progress / needs_answer / delivered se `sessionId`).
// Pracovník sedí u stolu (ticket na kartě), u společného stolu místnosti (ticket na sektoru) nebo v Recepci
// (ticket bez karty, nebo uzel mimo budovu). Čistá data bez Reactu; dílky je jen kreslí.
import { ticketTitle } from "@/layout/heart-channel/logic/tickets";
import type { AreaColor, CanvasNode, Graph } from "@/shared/types/logic/types";
import { nodeWorkflowOf, type DesktopState } from "@/shared/desktop-state/logic/types";
import { areaColorOf, areaLabel, isArea, membersOf } from "@/editor/canvas/area/logic/area-model";
import { cardState, type CardStateLine, type CardStateTone } from "@/editor/canvas/node-card/logic/card-state";
import { processView } from "@/editor/canvas/node-card/logic/card-process";
import type { WorkRow } from "@/editor/canvas/node-card/logic/use-work-overview";
import type { CardLease } from "@/editor/canvas/node-card/logic/use-leases";

/** Ticket z `GET /api/brain/tickets`, jen pole, která Kancelář čte (`WorkTicket` je splňuje). */
export type OfficeTicket = {
  ticketId: string; seq?: number; status: string; sessionId: string | null; updatedAt: string;
  body: { build: string }; machine: { cardId: string | null };
};
/** Pracovník: relace brány (`id` = `sessionId`) a ticket, který drží. */
export type Worker = { id: string; ticketId: string; title: string; nodeId: string | null; updatedAt: string };

/** Stavy, ve kterých ticket drží relace dělníka. */
const HELD = new Set(["claimed", "in_progress", "needs_answer", "delivered"]);
export type Desk = { id: string; name: string; closed: boolean; state: CardStateLine; workers: Worker[] };
export type ToneCounts = Record<CardStateTone, number>;
export type Room = { id: string; name: string; purpose: string; tones: ToneCounts; desks: Desk[]; common: Worker[] };
export type Department = { id: string; name: string; color: AreaColor; rooms: Room[] };
export type Office = { departments: Department[]; hall: Room[]; reception: Worker[] };

export type OfficeInput = {
  graph: Graph;
  tickets: OfficeTicket[];
  workRows?: Record<string, WorkRow>;
  leases?: Record<string, CardLease>;
  state: DesktopState;
};

export const UNNAMED_SECTOR = "Nepojmenovaný sektor";
export const UNNAMED_CARD = "Nepojmenovaná karta";
/** Pořadí tónů v pruhu stavů: hotovo, pracuje, čeká na člověka, selhalo, čeká (jako velín). */
export const TONE_ORDER: CardStateTone[] = ["ok", "run", "warn", "fail", "idle"];

const emptyTones = (): ToneCounts => ({ ok: 0, run: 0, warn: 0, fail: 0, idle: 0 });

/** Pracovníci: tickety držené relací, každá relace jednou (drží-li víc ticketů, platí první v seznamu). */
export function workersOf(tickets: OfficeTicket[]): Worker[] {
  const seen = new Set<string>();
  const workers: Worker[] = [];
  for (const t of tickets) {
    if (!HELD.has(t.status) || !t.sessionId || seen.has(t.sessionId)) continue;
    seen.add(t.sessionId);
    workers.push({ id: t.sessionId, ticketId: t.ticketId, title: ticketTitle(t), nodeId: t.machine.cardId, updatedAt: t.updatedAt });
  }
  return workers;
}

function deskOf(card: CanvasNode, input: OfficeInput): Omit<Desk, "workers"> {
  const flow = nodeWorkflowOf(input.state, card.id);
  const closed = !!flow.done?.confirmed;
  const own = input.state.nodes[card.id];
  const state = cardState({
    closed,
    doneProposed: !closed && flow.done?.by === "agent",
    process: processView(own?.stages ?? { profile: "custom", items: [] }),
    work: input.workRows?.[card.id],
    lease: input.leases?.[card.id],
  });
  return { id: card.id, name: card.name.trim() || UNNAMED_CARD, closed, state };
}

export function buildOffice(input: OfficeInput): Office {
  const { graph } = input;
  const workers = workersOf(input.tickets);
  const sectors = graph.nodes.filter((n) => n.kind === "sector");
  const sectorIds = new Set(sectors.map((s) => s.id));
  const cardSector = new Set(graph.nodes.filter((n) => n.kind === "node" && !!n.parentId && sectorIds.has(n.parentId)).map((n) => n.id));

  // Kam kdo sedí: karta ticketu je karta v budově → stůl; sektor v budově → společný stůl; jinak Recepce.
  const atDesk = new Map<string, Worker[]>();
  const atCommon = new Map<string, Worker[]>();
  const reception: Worker[] = [];
  const push = (map: Map<string, Worker[]>, key: string, w: Worker) => map.set(key, [...(map.get(key) ?? []), w]);
  for (const w of workers) {
    if (w.nodeId && cardSector.has(w.nodeId)) push(atDesk, w.nodeId, w);
    else if (w.nodeId && sectorIds.has(w.nodeId)) push(atCommon, w.nodeId, w);
    else reception.push(w);
  }

  const roomOf = (sector: CanvasNode): Room => {
    const desks = graph.nodes.filter((n) => n.kind === "node" && n.parentId === sector.id)
      .map((card) => ({ ...deskOf(card, input), workers: atDesk.get(card.id) ?? [] }));
    const tones = emptyTones();
    for (const d of desks) tones[d.state.tone]++;
    return { id: sector.id, name: sector.name.trim() || UNNAMED_SECTOR, purpose: sector.purpose.trim(), tones, desks, common: atCommon.get(sector.id) ?? [] };
  };

  const placed = new Set<string>();
  const departments: Department[] = graph.nodes.filter((n) => isArea(n) && n.parentId === null).map((area) => {
    const members = membersOf(area, graph.nodes).filter((n) => n.kind === "sector");
    members.forEach((m) => placed.add(m.id));
    return { id: area.id, name: areaLabel(area), color: areaColorOf(area), rooms: members.map(roomOf) };
  });
  const hall = sectors.filter((s) => !placed.has(s.id)).map(roomOf);
  return { departments, hall, reception };
}

/** Kolik pracovníků v budově sedí: u stolů, u společných stolů a v Recepci. */
export function workerCount(office: Office): number {
  const rooms = [...office.departments.flatMap((d) => d.rooms), ...office.hall];
  return rooms.reduce((sum, room) => sum + room.common.length + room.desks.reduce((n, desk) => n + desk.workers.length, 0), office.reception.length);
}
