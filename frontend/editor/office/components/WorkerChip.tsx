// Pracovník = relace brány, která drží úkol: název úkolu a krátké ID relace. Jen ukazuje, kdo kde
// pracuje; úkoly a odpovědi srdce jsou v panelu asistenta.
import type { Worker } from "../logic/office-model";

export default function WorkerChip({ worker }: { worker: Worker }) {
  return (
    <span className="office-worker" title={`${worker.title} · relace ${worker.id} · úkol ${worker.taskId}`}>
      <span className="office-worker__dot" aria-label="pracuje" />
      <span className="office-worker__title">{worker.title}</span>
      <span className="office-worker__session">{worker.id.slice(0, 8)}</span>
    </span>
  );
}
