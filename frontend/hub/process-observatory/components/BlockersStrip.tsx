import type { Lane } from "../logic/lanes";
import { ago } from "../logic/process-event";
import { CardHash, Chip } from "./Marks";

type Props = { lanes: Lane[]; now: number; onSelect: (nodeId: string) => void };

/** Pás blokací nad mapou: karty, jejichž poslední událost čeká na člověka nebo selhala. Bez blokací se neukáže. */
export default function BlockersStrip({ lanes, now, onSelect }: Props) {
  const blocked = lanes.filter((lane) => lane.blocker);
  if (!blocked.length) return null;
  return <section className="process-observatory__blockers" aria-label="Blokace" data-oh-field="blockers">
    <div className="process-observatory__blockers-head">
      <span className="process-observatory__blockers-title">Blokace · {blocked.length}</span>
      <span className="process-observatory__hint">needs.input · selhání · CI · požadované změny · guard</span>
    </div>
    <div className="process-observatory__blockers-list">
      {blocked.map((lane) => <div key={lane.nodeId} className="process-observatory__blocker" data-oh-blocker={lane.nodeId}>
        <Chip tone={lane.blocker!.tone}>{lane.blocker!.label}</Chip>
        <CardHash id={lane.nodeId} />
        <b className="process-observatory__blocker-title" title={lane.last?.title ?? lane.card?.reason}>{lane.title} — {lane.last?.title ?? lane.card?.reason}</b>
        <span className="process-observatory__mono process-observatory__muted">{ago(lane.lastMs, now)}</span>
        <button type="button" className="process-observatory__link" onClick={() => onSelect(lane.nodeId)}>Detail</button>
      </div>)}
    </div>
  </section>;
}
