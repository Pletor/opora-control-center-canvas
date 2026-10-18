// Recepce: relace bez karty i sektoru (hlavní relace projektu) a relace s vazbou mimo budovu.
import type { Worker } from "../logic/office-model";
import WorkerChip from "./WorkerChip";

export default function Reception({ workers, onSelectSession }: { workers: Worker[]; onSelectSession: (id: string) => void }) {
  return (
    <section className="office-reception" aria-label="Recepce">
      <h3 className="office-reception__name">Recepce</h3>
      <div className="office-reception__workers">
        {workers.length ? workers.map((w) => <WorkerChip key={w.id} worker={w} onSelect={onSelectSession} />)
          : <p className="office-reception__empty">Nikdo nečeká v recepci. Hlavní relace projektu se objeví tady.</p>}
      </div>
    </section>
  );
}
