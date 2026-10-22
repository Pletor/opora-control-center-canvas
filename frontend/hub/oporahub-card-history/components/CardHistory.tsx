import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import JsonMirror from "@/hub/oporahub-mirror/components/JsonMirror";
import { ToneChip } from "@/hub/oporahub-health/components/HealthMark";
import { blameRows, blameUrl, historyRows, historyUrl, parseBlame, parseHistory } from "../logic/card-history";
import "../styles/oporahub-card-history.css";

/** Historie a blame karty: odvozeno z přijatých changesetů na serveru, bez lokální kopie. */
export default function CardHistory({ project, workspace, nodeId }: { project: string; workspace: string; nodeId: string }) {
  const ready = !!project && !!workspace && !!nodeId;
  const history = useHubRead(ready ? historyUrl(project, workspace, nodeId) : null, parseHistory);
  const blame = useHubRead(ready ? blameUrl(project, workspace, nodeId) : null, parseBlame);
  const rows = history.data ? historyRows(history.data) : [];
  const owners = blame.data ? blameRows(blame.data) : [];
  const error = history.error || blame.error;
  return <section className="oporahub-card-history" data-oh-view="card-history" data-oh-node-id={nodeId} aria-label="Historie a blame karty">
    <JsonMirror id="oh-card-history" value={{ history: history.data, blame: blame.data }} />
    <header className="oporahub-card-history__head">
      <h2 className="oporahub-card-history__title">Historie a blame</h2>
      <span className="oporahub-card-history__note">přijaté revize · odvozeno z changesetů</span>
      <button type="button" className="oporahub-card-history__button" onClick={() => { history.reload(); blame.reload(); }}>Obnovit</button>
    </header>
    {error && <p className="oporahub-card-history__warning" role="alert">{error}</p>}
    {(history.busy || blame.busy) && !history.data && <p className="oporahub-card-history__note oporahub-card-history__pad" role="status">Načítám historii…</p>}
    <div className="oporahub-card-history__grid">
      <ol className="oporahub-card-history__list" aria-label="Přijaté revize karty" data-oh-list="card-history">
        {rows.map(row => <li key={row.revisionId} className="oporahub-card-history__item" data-oh-history-revision={row.revisionId} data-oh-proposal={row.proposalId}>
          <span className="oporahub-card-history__line">
            <code className="oporahub-card-history__mono">{row.short}</code>
            {row.current && <ToneChip tone="ok">✓ přijatá hlava</ToneChip>}
            <b className="oporahub-card-history__subject">{row.subject}</b>
          </span>
          <span className="oporahub-card-history__note">{row.author} · přijal {row.acceptedBy} · {row.acceptedAt}</span>
          {row.rebased && <span className="oporahub-card-history__rebased">↻ {row.rebased}</span>}
          <span className="oporahub-card-history__keys">{row.keys.map(key => <code key={key} className="oporahub-card-history__key">{key}</code>)}</span>
        </li>)}
        {history.data && !rows.length && <li className="oporahub-card-history__note">◌ Žádná přijatá revize se karty zatím nedotkla.</li>}
      </ol>
      <div className="oporahub-card-history__blame" role="table" aria-label="Blame karty">
        <div className="oporahub-card-history__row oporahub-card-history__row--head" role="row">
          {["klíč", "revize", "autor", "přijato"].map(name => <span key={name} role="columnheader">{name}</span>)}
        </div>
        {owners.map(row => <div key={row.key} role="row" className="oporahub-card-history__row" data-oh-blame-key={row.key} data-oh-revision={row.revisionId}>
          <code role="cell" className="oporahub-card-history__mono">{row.key}</code>
          <code role="cell" className="oporahub-card-history__mono">{row.short}</code>
          <span role="cell">{row.author}</span><span role="cell" className="oporahub-card-history__note">{row.acceptedAt}</span>
        </div>)}
        {blame.data && !owners.length && <p className="oporahub-card-history__note oporahub-card-history__pad">◌ Žádný klíč karty zatím nemá přijatou revizi.</p>}
      </div>
    </div>
  </section>;
}
