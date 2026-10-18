// Kancelář (docs/kancelar.md): plátno jako oddělení, místnosti a stoly, u kterých sedí relace asistenta.
// Rodič drží jen načtená data (relace, přehled práce, pronájmy, obsazenost) a poslední vybraného
// čekajícího; budovu skládá `logic/office-model.ts`, dílky jen kreslí. Nic tu neukládá: klik otevře
// kartu, vstoupí do vrstvy, nebo požádá App o novou relaci či výběr relace v panelu asistenta.
import { useMemo, useState } from "react";
import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { useWorkOverview } from "@/editor/canvas/node-card/logic/use-work-overview";
import { useLeases } from "@/editor/canvas/node-card/logic/use-leases";
import { useAssistantSessions } from "@/layout/assistant-panel/logic/use-assistant-sessions";
import { fetchStatus, type AssistantStatus } from "@/layout/assistant-panel/logic/assistant-api";
import type { StartRequest } from "@/layout/assistant-panel/logic/use-start-request";
import { buildOffice } from "../logic/office-model";
import { nextWaiting } from "../logic/next-waiting";
import { hireRequest, type HireTarget } from "../logic/hire-message";
import OfficeHeader from "./OfficeHeader";
import Department from "./Department";
import Room from "./Room";
import Reception from "./Reception";
import "../styles/office.css";

type Props = {
  project: string; workspace: string; graph: Graph; state: DesktopState;
  onOpenNode: (id: string) => void; onEnterLayer: (id: string) => void;
  /** Nová relace u stolu nebo místnosti; pořadové číslo přidělí App. */
  onStartSession: (request: Omit<StartRequest, "seq">) => void;
  onSelectSession: (id: string) => void;
};

/** Proč nejde posadit dalšího agenta, nebo `null`, když jde (stav neznámý = nebráníme, rozhodne server). */
function hireBlockReason(status: AssistantStatus | null): string | null {
  if (!status) return null;
  if (!status.available) return "Claude Code není dostupný.";
  if (status.running >= status.limit) return `Obsazeno: běží ${status.running} / ${status.limit}. Počkej, až některý agent doběhne.`;
  return null;
}

export default function OfficeWorkspace({ project, workspace, graph, state, onOpenNode, onEnterLayer, onStartSession, onSelectSession }: Props) {
  const revisionKey = JSON.stringify([graph.nodes.length, Object.keys(state.nodes).length]);
  const work = useWorkOverview(project, workspace, revisionKey);
  const leases = useLeases(project, workspace);
  const { sessions } = useAssistantSessions(true, true, project, workspace);
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  usePolling(() => fetchStatus().then(setStatus).catch(() => setStatus(null)), { intervalMs: 4000 });
  const [lastWaiting, setLastWaiting] = useState<string | null>(null);

  const office = useMemo(
    () => buildOffice({ graph, sessions, workRows: work?.data?.nodes, leases, state }),
    [graph, sessions, work?.data, leases, state],
  );
  const blocked = hireBlockReason(status);
  const hire = (target: HireTarget) => onStartSession(hireRequest(target, workspace));
  const next = () => {
    const id = nextWaiting(office.waiting, lastWaiting);
    if (!id) return;
    setLastWaiting(id);
    onSelectSession(id);
  };
  const roomProps = { blocked, onEnterLayer, onOpenNode, onHire: hire, onSelectSession };
  const empty = !office.departments.length && !office.hall.length;

  return (
    <section className="office" aria-label="Kancelář">
      <OfficeHeader waiting={office.waiting.length} running={status?.running ?? null} limit={status?.limit ?? null} onNext={next} />
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
        <Reception workers={office.reception} onSelectSession={onSelectSession} />
      </div>
    </section>
  );
}
