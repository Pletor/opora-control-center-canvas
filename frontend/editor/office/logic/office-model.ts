// Kancelář (docs/kancelar.md §1–2): z grafu, relací asistenta, přehledu práce a pronájmů složí budovu.
// Oddělení = oblast na kořenové vrstvě, místnost = sektor (člen oblasti podle polohy, jinak Hala),
// stůl = karta s `parentId` = sektor, pracovník = relace asistenta. Relace sedí u stolu (`nodeId`), u
// společného stolu místnosti (`sectorId`) nebo v Recepci (bez vazby, nebo vazba vede mimo budovu).
// Čistá data bez Reactu; dílky je jen kreslí.
import type { AreaColor, CanvasNode, Graph } from "@/shared/types/logic/types";
import { nodeWorkflowOf, type DesktopState } from "@/shared/desktop-state/logic/types";
import { areaColorOf, areaLabel, isArea, membersOf } from "@/editor/canvas/area/logic/area-model";
import { cardState, type CardStateLine, type CardStateTone } from "@/editor/canvas/node-card/logic/card-state";
import { processView } from "@/editor/canvas/node-card/logic/card-process";
import type { WorkRow } from "@/editor/canvas/node-card/logic/use-work-overview";
import type { CardLease } from "@/editor/canvas/node-card/logic/use-leases";
import type { AssistantSession } from "@/layout/assistant-panel/logic/assistant-api";

export type WorkerState = Exclude<AssistantSession["state"], "closed">;
export type Worker = { id: string; title: string; model: string; state: WorkerState; nodeId: string | null; sectorId: string | null; updatedAt: string };
export type Desk = { id: string; name: string; closed: boolean; state: CardStateLine; workers: Worker[] };
export type ToneCounts = Record<CardStateTone, number>;
export type Room = { id: string; name: string; purpose: string; tones: ToneCounts; desks: Desk[]; common: Worker[] };
export type Department = { id: string; name: string; color: AreaColor; rooms: Room[] };
export type Office = { departments: Department[]; hall: Room[]; reception: Worker[]; waiting: Worker[] };

export type OfficeInput = {
  graph: Graph;
  sessions: AssistantSession[];
  workRows?: Record<string, WorkRow>;
  leases?: Record<string, CardLease>;
  state: DesktopState;
};

export const UNNAMED_SECTOR = "Nepojmenovaný sektor";
export const UNNAMED_CARD = "Nepojmenovaná karta";
/** Pořadí tónů v pruhu stavů: hotovo, pracuje, čeká na člověka, selhalo, čeká (jako velín). */
export const TONE_ORDER: CardStateTone[] = ["ok", "run", "warn", "fail", "idle"];

const emptyTones = (): ToneCounts => ({ ok: 0, run: 0, warn: 0, fail: 0, idle: 0 });

function workerOf(s: AssistantSession): Worker {
  return { id: s.id, title: s.title, model: s.model, state: s.state as WorkerState, nodeId: s.nodeId ?? null, sectorId: s.sectorId ?? null, updatedAt: s.updatedAt };
}

function deskOf(card: CanvasNode, input: OfficeInput): Omit<Desk, "workers"> {
  const flow = nodeWorkflowOf(input.state, card.id);
  const closed = !!flow.done?.confirmed;
  const own = input.state.nodes[card.id];
  const state = cardState({
    closed,
    doneProposed: !closed && flow.done?.by === "agent",
    process: processView(own?.stages ?? { profile: "custom", items: [] }, own?.evidence, card.checks),
    work: input.workRows?.[card.id],
    lease: input.leases?.[card.id],
  });
  return { id: card.id, name: card.name.trim() || UNNAMED_CARD, closed, state };
}

export function buildOffice(input: OfficeInput): Office {
  const { graph } = input;
  const workers = input.sessions.filter((s) => s.state !== "closed").map(workerOf);
  const sectors = graph.nodes.filter((n) => n.kind === "sector");
  const sectorIds = new Set(sectors.map((s) => s.id));
  const cardSector = new Set(graph.nodes.filter((n) => n.kind === "node" && !!n.parentId && sectorIds.has(n.parentId)).map((n) => n.id));

  // Kam kdo sedí: karta v budově → stůl; jinak sektor v budově → společný stůl; jinak Recepce.
  const atDesk = new Map<string, Worker[]>();
  const atCommon = new Map<string, Worker[]>();
  const reception: Worker[] = [];
  const push = (map: Map<string, Worker[]>, key: string, w: Worker) => map.set(key, [...(map.get(key) ?? []), w]);
  for (const w of workers) {
    if (w.nodeId && cardSector.has(w.nodeId)) push(atDesk, w.nodeId, w);
    else if (!w.nodeId && w.sectorId && sectorIds.has(w.sectorId)) push(atCommon, w.sectorId, w);
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

  // Fronta majáků: nejstarší čekání první; stabilní řazení drží pořadí seznamu při shodném čase.
  const waiting = workers.map((w, i) => ({ w, i }))
    .filter(({ w }) => w.state === "waiting_approval")
    .sort((a, b) => a.w.updatedAt.localeCompare(b.w.updatedAt) || a.i - b.i)
    .map(({ w }) => w);
  return { departments, hall, reception, waiting };
}
