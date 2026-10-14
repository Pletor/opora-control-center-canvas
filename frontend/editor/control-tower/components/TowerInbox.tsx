// Fronta „Čeká na tebe“: jediné místo, kde člověk vidí, co od něj agenti chtějí. Jen čte a otevírá kartu.
// Bez přehledu práce nesmí tvrdit, že nic nečeká: otázky agentů jsou jen v přehledu, ne ve stavu plátna.
import ConfirmButton from "./ConfirmButton";
import { INBOX_LIMIT, groupInbox, type InboxFilter, type InboxItem, type InboxKind, type WorkState } from "../logic/tower-model";

const MARK: Record<InboxKind, { sign: string; label: string }> = {
  proposed: { sign: "✓", label: "ke schválení" },
  stuck: { sign: "⚠", label: "uvízlo" },
  waiting: { sign: "?", label: "otázka" },
};
const FILTERS: { key: InboxFilter; label: string }[] = [
  { key: "all", label: "Vše" }, { key: "proposed", label: "Ke schválení" }, { key: "stuck", label: "Uvízlo" }, { key: "waiting", label: "Otázky" },
];

type Props = {
  items: InboxItem[]; total: number; more: number; kinds: Record<InboxFilter, number>; filter: InboxFilter;
  workState: WorkState; workError?: string;
  /** Návrhy uzavření podle sektoru z celé fronty (ne jen viditelné stránky), pro „Potvrdit vše v sektoru“. */
  proposals: ReadonlyMap<string, string[]>;
  onConfirmProposal?: (nodeId: string) => Promise<boolean>;
  onConfirmSector?: (sectorId: string, ids: string[]) => Promise<void>;
  onFilter: (filter: InboxFilter) => void; onMore: () => void; onOpenNode: (id: string) => void;
};

export default function TowerInbox({ items, total, more, kinds, filter, workState, workError, proposals, onConfirmProposal, onConfirmSector, onFilter, onMore, onOpenNode }: Props) {
  const groups = groupInbox(items);
  const known = workState === "loaded";
  return (
    <aside className={"tower-inbox" + (known ? "" : " tower-inbox--partial")} aria-label="Čeká na tebe">
      <h2 className="tower-inbox__title">Čeká na tebe ({kinds.all}{known ? "" : "+?"})</h2>
      <div className="tower-inbox__filters" role="group" aria-label="Druh požadavku">
        {FILTERS.map((f) => (
          <button key={f.key} type="button" className={"tower-inbox__filter" + (filter === f.key ? " tower-inbox__filter--on" : "")}
            aria-pressed={filter === f.key} onClick={() => onFilter(f.key)}>
            {f.label} {kinds[f.key]}
          </button>
        ))}
      </div>
      {workState === "loading" && <p className="tower-inbox__notice">Načítám stav práce agentů…</p>}
      {workState === "unavailable" && (
        <p className="tower-inbox__notice tower-inbox__notice--error" role="alert">
          Stav práce není k dispozici{workError ? " (" + workError + ")" : ""}. Otázky agentů se nemusí ukázat.
        </p>
      )}
      {!total && known && <p className="tower-inbox__empty">{filter === "all" ? "Nic nečeká. Agenti pracují nebo je klid." : "Nic tohoto druhu nečeká."}</p>}
      {groups.map((group) => (
        <section key={group.key} className="tower-inbox__group">
          <h3 className="tower-inbox__group-title">{group.title}</h3>
          {onConfirmSector && group.sectorId && (proposals.get(group.sectorId)?.length ?? 0) >= 2 && (
            <div className="tower-inbox__group-action">
              <ConfirmButton label={"Potvrdit vše v sektoru (" + proposals.get(group.sectorId)!.length + ")"}
                action={() => onConfirmSector(group.sectorId, proposals.get(group.sectorId)!)} />
            </div>
          )}
          <ul className="tower-inbox__list">
            {group.items.map((item, index) => (
              <li key={item.kind + item.nodeId + index} className={"tower-inbox__item tower-inbox__item--" + item.kind}>
                <span className="tower-inbox__mark" title={MARK[item.kind].label} aria-label={MARK[item.kind].label}>{MARK[item.kind].sign}</span>
                <span className="tower-inbox__body">
                  <strong className="tower-inbox__name">{item.nodeName}</strong>
                  <span className="tower-inbox__text">{item.text}</span>
                </span>
                <span className="tower-inbox__actions">
                  {item.kind === "proposed" && onConfirmProposal && (
                    <ConfirmButton label="Potvrdit" action={() => onConfirmProposal(item.nodeId)} />
                  )}
                  <button type="button" className="tower-inbox__open" onClick={() => onOpenNode(item.nodeId)}>Otevřít</button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {more > 0 && (
        <button type="button" className="tower-inbox__more" onClick={onMore}>
          Zobrazit dalších {Math.min(INBOX_LIMIT, more)} (zbývá {more})
        </button>
      )}
    </aside>
  );
}
