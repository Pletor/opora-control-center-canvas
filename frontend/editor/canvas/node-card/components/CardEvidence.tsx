import { safeLinkUrl } from "../logic/safe-url";
export type Proof = { status: "pending" | "passed" | "failed" | "not_applicable"; url: string; note: string };
export type CompletionEvidence = { tests: Proof; review: Proof; merge: Proof;
  checksRun: { checkId: string; command: string; exitCode: number; logUrl: string; at: string }[] };

export default function CardEvidence({ evidence, autonomous }: { evidence?: CompletionEvidence; autonomous?: boolean }) {
  return <details className="nodrag nopan node-card__fold">
    <summary>{autonomous && <strong className="node-card__row-title">✓ Uzavřel agent · </strong>}
      <span className="node-card__row-title node-card__row-title--muted" title="Důkazy hlásí agent nebo člověk; server je nespouští ani neověřuje.">deklarováno:</span>
      {(["tests", "review", "merge"] as const).map(kind => {
      const proof = evidence?.[kind];
      // Testy lze doložit i lokálním během bez odkazu (checksRun s exit 0), stejně jako na serveru.
      const localRun = kind === "tests" && !!evidence?.checksRun.length && evidence.checksRun.every(run => run.exitCode === 0);
      const passed = proof?.status === "passed" && (safeLinkUrl(proof.url) || localRun);
      return <span key={kind} className={`node-card__chip node-card__chip--${passed ? "ok" : proof?.status === "failed" ? "fail" : "wait"}`} title={proof ? `${proof.note || kind} · deklarováno, neověřeno serverem` : "Důkaz nedoložen"}>
        {passed ? "✓" : proof?.status === "failed" ? "✗" : "○"} {kind === "tests" ? "Testy" : kind === "review" ? "Review" : "Merge"}
      </span>;
    })}</summary>
    <small>Deklarované důkazy (hlásí agent nebo člověk); server je nespouští a obsah odkazů neověřuje. Zelená = deklarováno, ne ověřeno.</small>
    {evidence && <>
      {(["tests", "review", "merge"] as const).map(kind => <p key={kind}>
        {kind}: {evidence[kind].status === "not_applicable" ? "Nevztahuje se" : evidence[kind].status} · {evidence[kind].note}
        {safeLinkUrl(evidence[kind].url) && <> · <a href={evidence[kind].url} target="_blank" rel="noopener noreferrer">Důkaz</a></>}
      </p>)}
      {evidence.checksRun.map(run => <p key={run.checkId}>
        {run.exitCode === 0 ? "✓" : "✗"} <code>{run.command}</code> · exit {run.exitCode} · {run.at}
        {safeLinkUrl(run.logUrl) && <> · <a href={run.logUrl} target="_blank" rel="noopener noreferrer">Log</a></>}
      </p>)}
    </>}
  </details>;
}
