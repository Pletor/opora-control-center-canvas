import { diffLines, type SiteProposal } from "../logic/site-proposals";
import "../styles/site-proposals.css";

/** Pruh „Srdce navrhuje změnu“ nad obsahem Správy webu: poznámka srdce, rozdíl po polích a Přijmout / Zamítnout.
 *  Dílek jen ukazuje; přijetí i zamítnutí hlásí nahoru, zapisuje rodič `SiteAdmin`. */
export default function SiteProposals({ proposal, busy, onAccept, onReject }: {
  proposal: SiteProposal; busy: boolean; onAccept: () => void; onReject: () => void;
}) {
  const lines = diffLines(proposal);
  const more = proposal.diffTotal - lines.length;
  return <section className="site-proposals" aria-label="Návrh změny od srdce" data-testid="site-proposal">
    <div className="site-proposals__head">
      <b className="site-proposals__title">Srdce navrhuje změnu</b>
      <span className="site-proposals__meta">nad revizí {proposal.baseRevision}{proposal.note ? ` · ${proposal.note}` : ""}</span>
      <button type="button" className="primary" disabled={busy} onClick={onAccept}>Přijmout</button>
      <button type="button" className="site-proposals__reject" disabled={busy} onClick={onReject}>Zamítnout</button>
    </div>
    <ul className="site-proposals__diff">
      {lines.map((line) => <li key={line.path} className="site-proposals__change">
        <code className="site-proposals__path">{line.path}</code>
        <span className="site-proposals__before">{line.before}</span>
        <span className="site-proposals__after">{line.after}</span>
      </li>)}
      {more > 0 && <li className="site-proposals__more">… a další změny ({more})</li>}
    </ul>
  </section>;
}
