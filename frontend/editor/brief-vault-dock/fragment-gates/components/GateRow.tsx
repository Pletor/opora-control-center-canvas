// Jedna brána v detailu fragmentu, jen zobrazení: tečka stavu, titulek, kdo bránu zapnul a kdy, uložený payload
// česky (u Ověřeno chyba předpovědi), poslední návrh brány s autorem a stavem (čeká / použit / zamítnut kým a proč)
// a důvod, proč cyklus stojí. Použitý návrh se jen jmenuje; jeho payload je už v záznamu brány.
import { formatError, GATE_TITLES, synthesizedView } from "@/editor/node-detail/brief-vault/logic/gate-bar";
import { shortWhen } from "../../logic/vault-dock-model";
import type { GateProposal } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { checkLines, runView } from "../logic/cell-view";
import { payloadLines, proposalStatus, verifiedOutcome, whoLabel, type GateRow as Row } from "../logic/gate-view";

export default function GateRow({ row, proposal }: { row: Row; proposal?: GateProposal }) {
  const state = row.on ? "on" : row.stale ? "stale" : row.next ? "next" : "off";
  const entry = row.entry;
  const lines = payloadLines(row.on || row.stale ? entry?.payload : null);
  const synth = row.gate === "synthesized" && (row.on || row.stale) ? synthesizedView(entry?.payload) : null;
  const error = row.gate === "verified" && row.on ? entry?.payload?.predictionError as number | undefined : undefined;
  const outcome = row.gate === "verified" && (row.on || row.stale) ? verifiedOutcome(entry?.payload?.actual) : null;
  const checks = row.gate === "synthesized" && (row.on || row.stale) ? checkLines(entry?.payload) : [];
  const run = row.gate === "verified" && (row.on || row.stale) ? runView(entry?.payload) : null;
  const status = row.on ? `potvrdil ${whoLabel(entry?.by, entry?.actor)} · ${shortWhen(entry?.at ?? "")}`
    : row.stale ? `zneplatněno změnou vstupů (zapnul ${whoLabel(entry?.by, entry?.actor)})`
    : row.next ? (proposal?.status === "pending" ? "čeká na potvrzení návrhu" : "další na řadě, čeká na návrh") : "vypnuto";
  return (
    <div className={"fragment-gates__row fragment-gates__row--" + state} data-testid={"gate-" + row.gate}>
      <span className={"brief-gates__dot brief-gates__dot--" + state} aria-hidden="true" />
      <div className="fragment-gates__body">
        <div className="fragment-gates__head">
          <strong title={GATE_TITLES[row.gate].hint}>{row.title}</strong>
          <span className="fragment-gates__state">{status}</span>
          {synth?.layer && <span className="fragment-gates__layer" title="Vrstva, do které mikrokrok patří" data-testid="synth-layer">{synth.layer}</span>}
          {error !== undefined && <span className="fragment-gates__error" title="Predikční chyba e = (testy + kola kritika + nečekané) / 3">chyba předpovědi {formatError(error)}</span>}
        </div>
        {outcome && (
          <div className="fragment-gates__outcome" data-testid="verified-outcome">
            <span className={"fragment-gates__badge fragment-gates__badge--" + (outcome.plan.approved ? "pass" : "fail")} data-testid="outcome-plan">{outcome.plan.text}</span>
            <span className={"fragment-gates__badge fragment-gates__badge--" + outcome.tests.state} data-testid="outcome-tests">{outcome.tests.text}</span>
          </div>
        )}
        {run && (
          <div className="fragment-gates__run" data-testid="verified-run">
            <span className="fragment-gates__badge" title="Server běh nespouští; nahlásil ho ověřovatel, nikdo ho neatestoval" data-testid="run-badge">{run.badge}</span>
            <span className="fragment-gates__state" data-testid="run-who">{run.who}</span>
            {run.checks.length > 0 && (
              <ul className="fragment-gates__payload" data-testid="run-checks">
                {run.checks.map((c) => <li key={c.checkId} className={"fragment-gates__run-check--" + (c.passed ? "pass" : "fail")}>{c.text}</li>)}
              </ul>
            )}
          </div>
        )}
        {checks.length > 0 && (
          <ul className="fragment-gates__payload" aria-label="Kontroly plánu" data-testid="synth-checks">{checks.map((c) => <li key={c.id}>{c.text}</li>)}</ul>
        )}
        {lines.length > 0 && <ul className="fragment-gates__payload">{lines.map((line) => <li key={line}>{line}</li>)}</ul>}
        {synth && synth.steps.length > 0 && (
          <ol className="fragment-gates__steps" aria-label="Kroky mikrokroku" data-testid="synth-steps">{synth.steps.map((step, i) => <li key={i}>{step}</li>)}</ol>
        )}
        {proposal && (
          <div className={"fragment-gates__proposal fragment-gates__proposal--" + proposal.status} aria-label="Poslední návrh brány"
            data-testid={"proposal-" + row.gate}>
            <span className="fragment-gates__state">{proposalStatus(proposal)} · {shortWhen(proposal.at)}{proposal.note ? ` · ${proposal.note}` : ""}</span>
            {proposal.status !== "used" && (
              <ul className="fragment-gates__payload">{payloadLines(proposal.payload).map((line) => <li key={line}>{line}</li>)}</ul>
            )}
          </div>
        )}
        {row.waiting && <span className="fragment-gates__waiting">{row.waiting}</span>}
      </div>
    </div>
  );
}
