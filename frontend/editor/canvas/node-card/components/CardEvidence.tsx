// Doklady karty rozepsané: tři důkazy (testy, review, merge) s odkazem a zdůvodněním a běhy kontrol s návratovým
// kódem; obsah foldu „Podrobnosti“ vybrané karty (stav karty nese tvář z agent-state).
import { safeLinkUrl } from "../logic/safe-url";
export type Proof = { status: "pending" | "passed" | "failed" | "not_applicable"; url: string; note: string };
export type CompletionEvidence = { tests: Proof; review: Proof; merge: Proof;
  checksRun: { checkId: string; command: string; exitCode: number; logUrl: string; at: string }[] };

const KIND_LABEL = { tests: "Testy", review: "Review", merge: "Merge" } as const;
const STATUS_LABEL = { pending: "nedoloženo", passed: "prošlo", failed: "selhalo", not_applicable: "Nevztahuje se" } as const;

/** Zelená jen s odkazem nebo úspěšným lokálním během; deklarace bez dokladu zůstává „čeká“. */
function chipState(kind: "tests" | "review" | "merge", proof: Proof, evidence: CompletionEvidence): "ok" | "fail" | "wait" {
  const localRun = kind === "tests" && !!evidence.checksRun.length && evidence.checksRun.every(run => run.exitCode === 0);
  if (proof.status === "passed" && (safeLinkUrl(proof.url) || localRun)) return "ok";
  return proof.status === "failed" ? "fail" : "wait";
}

export default function CardEvidence({ evidence, autonomous }: { evidence?: CompletionEvidence; autonomous?: boolean }) {
  return <div className="node-card__evidence">
    <small className="node-card__row-note" title="Důkazy hlásí agent přes agent-output.evidence; server je nespouští ani neověřuje.">{autonomous && <strong>✓ Uzavřel agent · </strong>}
      Deklarované důkazy: server je nespouští a obsah odkazů neověřuje.</small>
    {!evidence && <p className="node-card__row-note">Důkaz nedoložen</p>}
    {evidence && (["tests", "review", "merge"] as const).map(kind => {
      const proof = evidence[kind];
      const state = chipState(kind, proof, evidence);
      return <p key={kind}>
        <span className={`node-card__chip node-card__chip--${state}`}>{state === "ok" ? "✓" : state === "fail" ? "✗" : "○"} {KIND_LABEL[kind]}</span>
        {" "}{STATUS_LABEL[proof.status]}{proof.note ? ` · ${proof.note}` : ""}
        {safeLinkUrl(proof.url) && <> · <a href={proof.url} target="_blank" rel="noopener noreferrer">Důkaz</a></>}
      </p>;
    })}
    {evidence?.checksRun.map(run => <p key={run.checkId}>
      {run.exitCode === 0 ? "✓" : "✗"} <code>{run.command}</code> · exit {run.exitCode} · {run.at}
      {safeLinkUrl(run.logUrl) && <> · <a href={run.logUrl} target="_blank" rel="noopener noreferrer">Log</a></>}
    </p>)}
  </div>;
}
