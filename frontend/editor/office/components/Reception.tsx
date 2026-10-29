// Recepce: pracovníci, jejichž úkol nemá uzel, nebo jeho uzel v budově není.
import type { Worker } from "../logic/office-model";
import WorkerChip from "./WorkerChip";

export default function Reception({ workers }: { workers: Worker[] }) {
  return (
    <section className="office-reception" aria-label="Recepce">
      <h3 className="office-reception__name">Recepce</h3>
      <div className="office-reception__workers">
        {workers.length ? workers.map((w) => <WorkerChip key={w.id} worker={w} />)
          : <p className="office-reception__empty">Nikdo nečeká v recepci. Pracovníci s úkolem bez karty se objeví tady.</p>}
      </div>
    </section>
  );
}
