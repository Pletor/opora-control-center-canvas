import { safeDesignUrl } from "./CardDesign";
export type Proof = { status: "pending" | "passed" | "failed" | "not_applicable"; url: string; note: string };
export type CompletionEvidence = { tests: Proof; review: Proof; merge: Proof;
  checksRun: { checkId: string; command: string; exitCode: number; logUrl: string; at: string }[] };

export default function CardEvidence({ evidence, autonomous }: { evidence?: CompletionEvidence; autonomous?: boolean }) {
  return <details className="nodrag nopan" style={{ padding: "6px 12px" }}>
    <summary>{autonomous && <strong>✓ 🤖 Uzavřel agent · </strong>}
      <span title="Důkazy hlásí agent nebo člověk; server je nespouští ani neověřuje." style={{ marginRight: 8, fontStyle: "italic", color: "#64748b" }}>deklarováno:</span>
      {(["tests", "review", "merge"] as const).map(kind => {
      const proof = evidence?.[kind];
      // Testy lze doložit i lokálním během bez odkazu (checksRun s exit 0), stejně jako na serveru.
      const localRun = kind === "tests" && !!evidence?.checksRun.length && evidence.checksRun.every(run => run.exitCode === 0);
      const passed = proof?.status === "passed" && (safeDesignUrl(proof.url) || localRun);
      return <span key={kind} title={proof ? `${proof.note || kind} · deklarováno, neověřeno serverem` : "Důkaz nedoložen"} style={{ marginRight: 8,
        color: passed ? "#16a34a" : proof?.status === "failed" ? "#dc2626" : "#64748b" }}>
        {passed ? "✓" : proof?.status === "failed" ? "✗" : "○"} {kind === "tests" ? "Testy" : kind === "review" ? "Review" : "Merge"}
      </span>;
    })}</summary>
    <small>Deklarované důkazy (hlásí agent nebo člověk); server je nespouští a obsah odkazů neověřuje. Zelená = deklarováno, ne ověřeno.</small>
    {evidence && <>
      {(["tests", "review", "merge"] as const).map(kind => <p key={kind}>
        {kind}: {evidence[kind].status === "not_applicable" ? "Nevztahuje se" : evidence[kind].status} · {evidence[kind].note}
        {safeDesignUrl(evidence[kind].url) && <> · <a href={evidence[kind].url} target="_blank" rel="noopener noreferrer">Důkaz</a></>}
      </p>)}
      {evidence.checksRun.map(run => <p key={run.checkId}>
        {run.exitCode === 0 ? "✓" : "✗"} <code>{run.command}</code> · exit {run.exitCode} · {run.at}
        {safeDesignUrl(run.logUrl) && <> · <a href={run.logUrl} target="_blank" rel="noopener noreferrer">Log</a></>}
      </p>)}
    </>}
  </details>;
}
