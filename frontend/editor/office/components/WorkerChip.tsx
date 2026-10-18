// Pracovník = relace asistenta: jméno, model a stav tečkou (čekající na schválení = pulzující maják).
// Klik přepne panel asistenta na tuto relaci.
import type { Worker, WorkerState } from "../logic/office-model";

const STATE_LABEL: Record<WorkerState, string> = {
  running: "pracuje", waiting_approval: "čeká na tvé schválení", idle: "v klidu", error: "chyba",
};

export default function WorkerChip({ worker, onSelect }: { worker: Worker; onSelect: (id: string) => void }) {
  const label = STATE_LABEL[worker.state] ?? worker.state;
  return (
    <button type="button" className={"office-worker office-worker--" + worker.state} onClick={() => onSelect(worker.id)}
      title={`${worker.title} · ${worker.model} · ${label}`}>
      <span className="office-worker__dot" aria-label={label} />
      <span className="office-worker__title">{worker.title}</span>
      <span className="office-worker__model">{worker.model}</span>
    </button>
  );
}
