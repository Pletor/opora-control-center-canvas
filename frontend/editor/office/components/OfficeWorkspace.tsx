import type { WorkScope } from "@/shared/work-scope/logic/work-scope";
import { scopedOffice } from "../logic/office-scope";
// Kancelář (docs/kancelar.md): plátno jako oddělení, místnosti a stoly, u kterých sedí pracovníci brány.
// Rodič drží jen načtená data (tickety práce, přehled práce, pronájmy, stav srdce); budovu skládá
// `logic/office-model.ts`, dílky jen kreslí. Nic tu neukládá: klik otevře kartu, vstoupí do vrstvy,
// nebo pošle App připravený text pro srdce (App ho odešle a otevře panel asistenta).
import { useMemo, useState } from "react";
import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { useWorkOverview } from "@/editor/canvas/node-card/logic/use-work-overview";
import { useLeases } from "@/editor/canvas/node-card/logic/use-leases";
import { fetchHeartStatus, fetchTickets, type HeartRequest, type HeartStatus, type WorkTicket } from "@/layout/heart-channel/logic/heart-api";
import { workerCount } from "../logic/office-model";
import { hireRequest, type HireTarget } from "../logic/hire-message";
import OfficeHeader from "./OfficeHeader";
import Department from "./Department";
import Room from "./Room";
import Reception from "./Reception";
import "../styles/office.css";

type Props = {
  workScope: WorkScope; project: string; workspace: string; graph: Graph; state: DesktopState;
  onOpenNode: (id: string) => void; onEnterLayer: (id: string) => void;
  /** Posadit agenta: připravený text pro srdce; odešle ho App. */
  onAskHeart: (request: HeartRequest) => void;
};

/** Proč nejde posadit agenta, nebo `null`, když jde (stav neznámý = nebráníme, rozhodne server). */
function hireBlockReason(status: HeartStatus | null): string | null {
  if (status && !status.enabled) return "Srdce je u projektu vypnuté. Zapni bránu v panelu asistenta.";
  return null;
}

export default function OfficeWorkspace({ workScope, project, workspace, graph, state, onOpenNode, onEnterLayer, onAskHeart }: Props) {
  const revisionKey = JSON.stringify([graph.nodes.length, Object.keys(state.nodes).length]);
  const work = useWorkOverview(project, workspace, revisionKey);
  const leases = useLeases(project, workspace);
  const [tickets, setTickets] = useState<WorkTicket[]>([]);
  const [status, setStatus] = useState<HeartStatus | null>(null);
  usePolling(() => Promise.all([
    fetchTickets(project, workspace).then(setTickets).catch(() => setTickets([])),
    fetchHeartStatus(project).then(setStatus).catch(() => setStatus(null)),
  ]), { intervalMs: 4000, enabled: !!project && !!workspace });

  const office = useMemo(
    () => scopedOffice({ graph, tickets, workRows: work?.data?.nodes, leases, state }, workScope),
    [graph, tickets, work?.data, leases, state, workScope.projectId, workScope.nodeId],
  );
  const blocked = hireBlockReason(status);
  const hire = (target: HireTarget) => onAskHeart(hireRequest(target, workspace));
  const roomProps = { blocked, onEnterLayer, onOpenNode, onHire: hire };
  const empty = !office.departments.length && !office.hall.length;

  return (
    <section className="office" aria-label="Kancelář">
      <OfficeHeader status={status} workers={workerCount(office)} />
      <div className="office__floor">
        {office.departments.map((d) => (
          <Department key={d.id} name={d.name} color={d.color} empty={!d.rooms.length}>
            {d.rooms.map((room) => <Room key={room.id} room={room} {...roomProps} />)}
          </Department>
        ))}
        {office.hall.length > 0 && (
          <Department name="Hala" color={null} empty={false}>
            {office.hall.map((room) => <Room key={room.id} room={room} {...roomProps} />)}
          </Department>
        )}
        {empty && <p className="office__empty">V budově zatím nejsou místnosti. Kancelář ukáže sektory a karty, jakmile na plátně vzniknou.</p>}
        <Reception workers={office.reception} />
      </div>
    </section>
  );
}
