import type { FlowVersion } from "@/shared/flow-editor/logic/flow-types";

type Props = { proposal: FlowVersion; summary: string | null; viewing: boolean; busy: boolean; onView: () => void; onAccept: () => void; onReject: () => void };

/** Čekající návrh srdce u plátna člověka (knihovna §5): poznámka srdce, rozdíl proti aktivní verzi a rozhodnutí
 * jedním klikem. Přijmout = aktivovat draft, Zamítnout = draft do historie s důvodem. Zápis drží `LibraryCanvas`. */
export default function ProposalBar({ proposal, summary, viewing, busy, onView, onAccept, onReject }: Props) {
  return <div className="library-versions library-versions--proposal" role="region" aria-label="Návrh srdce" data-testid="library-proposal">
    <span className="library-versions__proposal-text">Srdce navrhuje změnu: <b>{proposal.meta?.note || "bez poznámky"}</b> (v{proposal.n})</span>
    {viewing && summary && <span className="library-versions__diff" data-testid="library-proposal-diff">{summary}</span>}
    <span className="library-versions__actions">
      {!viewing && <button type="button" className="library-versions__button" disabled={busy} onClick={onView}>Ukázat návrh</button>}
      <button type="button" className="library-versions__button library-versions__button--primary" disabled={busy} data-testid="library-proposal-accept" onClick={onAccept}>Přijmout</button>
      <button type="button" className="library-versions__button" disabled={busy} data-testid="library-proposal-reject" onClick={onReject}>Zamítnout</button>
    </span>
  </div>;
}
