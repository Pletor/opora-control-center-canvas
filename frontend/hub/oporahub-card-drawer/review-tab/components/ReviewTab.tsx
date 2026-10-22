import CardProofs from "@/hub/oporahub-proofs/components/CardProofs";
import { gateView } from "@/hub/oporahub-review-gate/logic/gate-view";
import type { CardData } from "../../logic/use-card-data";
import { cardFindings, freshness, gateRules, severityCounts, SEVERITY_LABEL, STATUS_LABEL } from "../logic/review-view";
import "../styles/review-tab.css";

const RULE_GLYPH = { ok: "✓", pending: "◷", blocked: "✕", off: "◌" } as const;
const STATUS = { ready: { glyph: "✓", word: "splněna" }, pending: { glyph: "◷", word: "čeká" }, blocked: { glyph: "✕", word: "drží" } } as const;

/** Záložka Review & PR: PR a čerstvost, pravidla brány se všemi důvody, nálezy, lidé a formální důkazy. */
export default function ReviewTab({ project, workspace, nodeId, data }: { project: string; workspace: string; nodeId: string; data: CardData }) {
  const gate = data.gate;
  const view = gate ? gateView(gate, data.agent?.actions ?? []) : null;
  const findings = cardFindings(data.findings, gate), counts = severityCounts(findings);
  const fresh = gate ? freshness(gate) : null;
  const template = gate?.mergeReadiness.template;
  return <div className="review-tab" data-oh-view="card-review" data-oh-node-id={nodeId} data-oh-pr-number={gate?.number ?? ""}
    data-oh-head-sha={gate?.headSha ?? ""} data-oh-gate-status={gate?.reviewGate.status ?? "none"} data-oh-gate-rule={view?.rule ?? ""}>
    {!gate ? <p className="review-tab__empty" data-oh-review-gate="" data-oh-gate-status="none">
      ◌ Karta zatím nemá PR navázané na běh{data.card?.gate ? ` (agent-state: brána ${data.card.gate.status})` : ""}; brána review se nepočítá.</p> : <>
      <section className="review-tab__pr" data-oh-pr-link={`${gate.repository}#${gate.number}`} data-oh-pr-state={gate.prState}>
        <div className="review-tab__pr-line"><code className="review-tab__pr-number">PR #{gate.number}</code>
          <b>{gate.repository}</b><span className={`review-tab__chip review-tab__chip--${gate.prState === "open" ? "gap" : "ok"}`}>{gate.prState}</span></div>
        <div className="review-tab__pr-line review-tab__muted">
          <code>{gate.headSha.slice(0, 12)}</code> → {gate.mergeReadiness.base?.baseRef ?? "cíl?"}
          {" · "}{template ? (template.missing.length ? `šablona: chybí ${template.missing.join(", ")}` : "šablona ✓") : "šablona neověřena"}
          {gate.riskTier && ` · riziko ${gate.riskTier}`}{gate.round !== null && ` · kolo ${gate.round}`}
          {fresh && <span className={`review-tab__chip review-tab__chip--${fresh.tone}`} data-oh-freshness={fresh.tone}>{fresh.tone === "ok" ? "✓" : "◷"} {fresh.text}</span>}
        </div>
      </section>
      <section className="review-tab__section" aria-label="Brána merge" data-oh-review-gate={gate.executionId}>
        <h3 className="review-tab__heading">Brána {view?.rule && <code className="review-tab__muted">{view.rule}</code>}
          <span className={`review-tab__chip review-tab__chip--${gate.reviewGate.status === "ready" ? "ok" : gate.reviewGate.status === "blocked" ? "bad" : "warn"}`}>
            {STATUS[gate.reviewGate.status].glyph} {STATUS[gate.reviewGate.status].word}{gate.reviewGate.reasons.length ? ` · ${gate.reviewGate.reasons.length} důvodů` : ""}</span></h3>
        <ul className="review-tab__list">{gateRules(gate).map(rule => <li key={rule.code} className={`review-tab__rule review-tab__rule--${rule.state}`}
          data-oh-gate-reason={rule.code} data-oh-rule-state={rule.state}>
          <span aria-hidden="true">{RULE_GLYPH[rule.state]}</span><span>{rule.label}{rule.detail && <span className="review-tab__muted"> · {rule.detail}</span>}</span>
          {rule.state !== "ok" && rule.state !== "off" && <code className="review-tab__muted">{rule.code}</code>}</li>)}</ul>
      </section>
      <section className="review-tab__section" aria-label="Nálezy review" data-oh-findings-open={counts.open} data-oh-findings-important={counts.important}>
        <h3 className="review-tab__heading">Nálezy <span className="review-tab__muted">{counts.open} otevřených · {counts.total} celkem</span></h3>
        {findings.length ? <ul className="review-tab__list">{findings.map(item => <li key={item.findingId} className={`review-tab__finding review-tab__finding--${item.status === "open" ? "open" : "closed"}`}
          data-oh-finding={item.findingId} data-oh-severity={item.severity} data-oh-finding-status={item.status}>
          <span aria-hidden="true">{item.status === "open" ? "✕" : "✓"}</span>
          <span><b>{item.title}</b><span className="review-tab__muted"> {SEVERITY_LABEL[item.severity] ?? item.severity}{item.path && ` · ${item.path}${item.line ? `:${item.line}` : ""}`}{item.round !== null && ` · kolo ${item.round}`}</span></span>
          <span className={`review-tab__chip review-tab__chip--${item.status === "open" ? "bad" : "ok"}`}>{STATUS_LABEL[item.status] ?? item.status}</span></li>)}</ul>
          : <p className="review-tab__muted">Žádné nálezy review pro toto PR.</p>}
      </section>
      {view && <section className="review-tab__section" aria-label="Ověření lidé" data-oh-approvals-required={view.approvals.required}
        data-oh-approvals-verified={view.approvals.counted} data-oh-humans-mode={view.approvals.mode}>
        <h3 className="review-tab__heading">Ověření lidé <span className="review-tab__muted">{view.approvals.counted}/{view.approvals.required} · {view.approvals.label}</span></h3>
        <ul className="review-tab__list">{(gate.reviewGate.humans?.identityIds ?? []).map(id => <li key={id} className="review-tab__rule review-tab__rule--ok" data-oh-identity={id}>
          <span aria-hidden="true">✓</span><span>{id}</span></li>)}
          {view.approvals.counted < view.approvals.required && <li className="review-tab__rule review-tab__rule--pending"><span aria-hidden="true">○</span>
            <span>Chybí {view.approvals.required - view.approvals.counted} schválení na aktuální hlavě</span></li>}</ul>
        {view.approvals.notes.map(note => <p key={note} className="review-tab__muted">{note}</p>)}
      </section>}
    </>}
    <CardProofs project={project} workspace={workspace} nodeId={nodeId} state={data.agent} />
  </div>;
}
