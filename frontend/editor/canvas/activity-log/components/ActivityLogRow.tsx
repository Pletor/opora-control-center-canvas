// Jeden zápis: čas, u agenta žeton se jménem, akce z cesty s doplňkem, karty (klik = otevřít kartu)
// a tichý status; selhaný zápis nese červený proužek a „selhalo · 409“. Akce z plné autonomie nese štítek.
import Icon from "@/ui-kit/icon/components/Icon";
import { actionLabel, isFailed, isFullAutonomy, nodeRefs, summaryDetail, timeLabel, type ActivityEntry } from "@/editor/canvas/activity-log/logic/activity-log";

export default function ActivityLogRow({ entry, nodes, onOpenNode }: {
  entry: ActivityEntry;
  nodes: { id: string; name: string }[];
  onOpenNode: (id: string) => void;
}) {
  const failed = isFailed(entry.status);
  const detail = summaryDetail(entry.summary);
  const refs = nodeRefs(entry.nodeIds, nodes);
  return (
    <li className={`activity-log__row activity-log__row--${entry.actor}` + (failed ? " activity-log__row--failed" : "")}
      title={`${entry.method} ${entry.path} · ${entry.status}${entry.summary ? " · " + entry.summary : ""}`}>
      <time className="activity-log__time" dateTime={entry.at}>{timeLabel(entry.at)}</time>
      <div className="activity-log__body">
        <div className="activity-log__line">
          {entry.actor === "agent" && (
            <span className="activity-log__agent"><Icon name="bot" size={16} />{entry.agent || "agent"}</span>
          )}
          {isFullAutonomy(entry) && (
            <span className="activity-log__autonomy" title="Agent to udělal díky plné autonomii projektu">plná autonomie</span>
          )}
          <span className="activity-log__action">{actionLabel(entry.path)}</span>
          {detail && <span className="activity-log__detail">{detail}</span>}
        </div>
        {refs.length > 0 && (
          <div className="activity-log__nodes">
            {refs.map((ref) => ref.known
              ? <button key={ref.id} type="button" className="activity-log__node" onClick={() => onOpenNode(ref.id)} title="Otevřít kartu na plátně">{ref.name}</button>
              : <span key={ref.id} className="activity-log__node activity-log__node--missing" title="Karta není v grafu plátna">{ref.name}</span>)}
          </div>
        )}
      </div>
      <span className={"activity-log__status" + (failed ? " activity-log__status--failed" : "")}>
        {failed ? `selhalo · ${entry.status}` : entry.status}
      </span>
    </li>
  );
}
