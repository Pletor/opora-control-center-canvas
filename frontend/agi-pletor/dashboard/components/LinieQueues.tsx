import type { Queue, QueueId } from "../logic/linie-queues";

type Props = { queues: Queue[]; active: QueueId | ""; onPick: (id: QueueId | "") => void };

/**
 * Fronty odpovědnosti nad lištou: kdo má míč. Klik na frontu ztlumí ostatní kuličky (měřítko ani posun nemění),
 * druhý klik filtr zruší. Fronta bez zdroje se nedá zvolit a říká to.
 */
export default function LinieQueues({ queues, active, onPick }: Props) {
  return (
    <div className="pletor-dashboard__linie-queues" role="group" aria-label="Fronty odpovědnosti">
      {queues.map((queue) => (
        <button key={queue.id} type="button" className={`pletor-dashboard__linie-queue${queue.source ? "" : " pletor-dashboard__linie-queue--nosource"}`}
          aria-pressed={active === queue.id} disabled={!queue.source} title={queue.hint}
          onClick={() => onPick(active === queue.id ? "" : queue.id)}>
          <span className="pletor-dashboard__linie-queue-label">{queue.label}</span>
          <span className="pletor-dashboard__linie-queue-count">{queue.count}</span>
          <span className="pletor-dashboard__linie-queue-hint">{queue.hint}</span>
        </button>
      ))}
    </div>
  );
}
