// Seznam zápisů jedné záložky po dnech (Dnes, Včera, datum) a dole Načíst starší. Jen se posouvá
// seznam; hlavička panelu a záložky stojí.
import ActivityLogRow from "@/editor/canvas/activity-log/components/ActivityLogRow";
import type { ActorLog } from "@/editor/canvas/activity-log/logic/use-activity-log";
import { groupByDay, type Actor } from "@/editor/canvas/activity-log/logic/activity-log";

export default function ActivityLogList({ actor, log, nodes, onLoadOlder, onOpenNode }: {
  actor: Actor;
  log: ActorLog;
  nodes: { id: string; name: string }[];
  onLoadOlder: () => void;
  onOpenNode: (id: string) => void;
}) {
  const groups = groupByDay(log.entries);
  return (
    <div className="activity-log__scroll" role="tabpanel">
      {log.loading && log.entries.length === 0 && <p className="activity-log__empty">Načítám záznam…</p>}
      {!log.loading && log.entries.length === 0 && !log.error && (
        <p className="activity-log__empty">{actor === "human" ? "Zatím žádný tvůj zápis." : "Zatím žádný zápis agenta."}</p>
      )}
      {groups.map((group) => (
        <section key={group.key} className="activity-log__day" aria-label={group.label}>
          <h3 className="activity-log__day-title">{group.label}<span className="activity-log__day-count">{group.entries.length}</span></h3>
          <ul className="activity-log__list">
            {group.entries.map((entry) => <ActivityLogRow key={entry.id} entry={entry} nodes={nodes} onOpenNode={onOpenNode} />)}
          </ul>
        </section>
      ))}
      {log.nextBefore !== null && (
        <button type="button" className="activity-log__older" disabled={log.loading} onClick={onLoadOlder} data-testid="activity-log-older">
          {log.loading ? "Načítám…" : "Načíst starší"}
        </button>
      )}
    </div>
  );
}
