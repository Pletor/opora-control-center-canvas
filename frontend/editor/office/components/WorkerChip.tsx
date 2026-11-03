// Pracovník = relace brány, která drží ticket: titulek ticketu a krátké ID relace. Jen ukazuje, kdo kde
// pracuje; tickety a odpovědi srdce jsou v panelu asistenta.
import type { Worker } from "../logic/office-model";

export default function WorkerChip({ worker }: { worker: Worker }) {
  return (
    <span className="office-worker" title={`${worker.title} · relace ${worker.id} · ticket ${worker.ticketId}`}>
      <span className="office-worker__dot" aria-label="pracuje" />
      <span className="office-worker__title">{worker.title}</span>
      <span className="office-worker__session">{worker.id.slice(0, 8)}</span>
    </span>
  );
}
