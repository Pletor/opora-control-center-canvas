import type { AgentState } from "@/hub/oporahub-agent-state/logic/agent-state";
import HealthMark, { ToneChip } from "@/hub/oporahub-health/components/HealthMark";
import JsonMirror from "@/hub/oporahub-mirror/components/JsonMirror";
import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import { cardGates, gatesEndpoint, parseGates } from "../logic/review-gate";
import { gateView, type GateView } from "../logic/gate-view";
import "../styles/oporahub-review-gate.css";

type Props = { project: string; workspace: string; nodeId: string; state: AgentState | null };
type Tone = "ok" | "warn" | "bad" | "gap";
const TONE: Record<string, Tone> = { ok: "ok", pending: "warn", missing: "warn", blocked: "bad", failed: "bad", off: "gap" };
const GLYPH: Record<Tone, string> = { ok: "✓", warn: "◷", bad: "✕", gap: "◌" };

function Fact({ label, tone, text }: { label: string; tone: Tone; text: string }) {
  return <div className="oporahub-review-gate__fact">
    <span className="oporahub-review-gate__label">{label}</span>
    <ToneChip tone={tone}>{GLYPH[tone]} {text}</ToneChip>
  </div>;
}

function GateBody({ view }: { view: GateView }) {
  const approvalsTone: Tone = view.approvals.counted >= view.approvals.required ? "ok" : "warn";
  const templateTone: Tone = view.template.on ? "warn" : view.template.text === "pravidlo vypnuto" ? "gap" : "ok";
  return <div className="oporahub-review-gate__gate" data-oh-review-gate={view.executionId} data-oh-gate-status={view.status}
    data-oh-gate-rule={view.rule} data-oh-open-important={view.openImportant} data-oh-security={view.security.state}
    data-oh-approvals-required={view.approvals.required} data-oh-approvals-verified={view.approvals.counted}
    data-oh-humans-mode={view.approvals.mode} data-oh-self-checks={view.selfChecks.status}
    data-oh-stale-against-main={String(view.stale.on)} data-oh-template-incomplete={String(view.template.on)}>
    <div className="oporahub-review-gate__status">
      <HealthMark health={view.health} text={`brána ${view.statusWord}`} />
      <code className="oporahub-review-gate__mono">{view.pr} · {view.head} · {view.prState}</code>
    </div>
    <p className="oporahub-review-gate__rule"><b>Drží ji:</b> {view.ruleText}{view.rule && <code className="oporahub-review-gate__mono"> {view.rule}</code>}</p>
    {view.reasons.length > 0 && <div className="oporahub-review-gate__chips">
      {view.reasons.map(item => <span key={item.code} title={item.text} data-oh-gate-reason={item.code}>
        <ToneChip tone={view.status === "blocked" ? "bad" : "warn"}>{item.code}</ToneChip></span>)}
    </div>}
    <div className="oporahub-review-gate__facts">
      <Fact label="Otevřené důležité nálezy" tone={view.openImportant ? "bad" : "ok"} text={String(view.openImportant)} />
      <Fact label="Bezpečnostní review" tone={TONE[view.security.state] ?? "warn"} text={view.security.text} />
      <Fact label={`Schválení · ${view.approvals.label}`} tone={approvalsTone} text={`${view.approvals.counted} z ${view.approvals.required}`} />
      <Fact label="Vlastní kontroly agenta" tone={TONE[view.selfChecks.status] ?? "warn"}
        text={`${view.selfChecks.status}${view.selfChecks.detail ? ` · ${view.selfChecks.detail}` : ""}`} />
      <Fact label="Proti cílové větvi" tone={view.stale.on ? "warn" : "ok"} text={view.stale.text} />
      <Fact label="Šablona PR" tone={templateTone} text={view.template.text} />
    </div>
    {view.security.reasons.length > 0 && <p className="oporahub-review-gate__note">Proč bezpečnostní review: {view.security.reasons.join(", ")}</p>}
    {view.approvals.notes.map(note => <p key={note} className="oporahub-review-gate__note">{note}</p>)}
    {view.actions.length > 0 && <ul className="oporahub-review-gate__actions" aria-label="Akce agenta pro bránu">
      {view.actions.map(item => <li key={item.id} data-oh-action-id={item.id} data-oh-verb={item.verb} data-oh-action-status={item.status}>
        <b className="oporahub-review-gate__mono">{item.verb}</b>{" "}
        <ToneChip tone={item.status === "ready" ? "ok" : "bad"}>{item.status === "ready" ? "✓ připraveno" : `✕ ${item.blockReason}`}</ToneChip>
      </li>)}
    </ul>}
  </div>;
}

/** Krok Review: brána merge karty z `GET …/review-jobs/gates`; akce agenta z agent-state. */
export default function CardReviewGate({ project, workspace, nodeId, state }: Props) {
  const read = useHubRead(project && workspace ? gatesEndpoint(project, workspace) : null, parseGates);
  const gates = cardGates(read.data ?? [], nodeId);
  return <section className="oporahub-review-gate" aria-label="Review a brána merge" data-oh-step="review">
    <header className="oporahub-review-gate__head"><h2 className="oporahub-review-gate__title">Review · brána merge</h2>
      <button type="button" className="oporahub-review-gate__ghost" onClick={read.reload} disabled={read.busy}>Obnovit</button></header>
    <JsonMirror id="oh-review-gates" value={gates} />
    <div className="oporahub-review-gate__body">
      {read.busy && !read.data && <p className="oporahub-review-gate__note" role="status">Načítám bránu review…</p>}
      {read.error && <p className="oporahub-review-gate__note" role="alert">{read.error}</p>}
      {read.data && !gates.length && <p className="oporahub-review-gate__note" data-oh-review-gate="" data-oh-gate-status="none">
        ◌ Brána review se pro kartu zatím nepočítá (žádné PR navázané na běh, nebo automatické review vypnuté).</p>}
      {gates.map(gate => <GateBody key={`${gate.executionId}:${gate.number}`} view={gateView(gate, state?.actions ?? [])} />)}
    </div>
  </section>;
}
