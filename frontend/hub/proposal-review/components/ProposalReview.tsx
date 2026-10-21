import { useState } from "react";
import { riskLabels, REVIEW_ROOT, reviewQuery, type ReviewEvent } from "../logic/proposal-review";
import type { ProposalReviewView } from "../logic/use-proposal-review";
import { riskReasonLabel, blockedReasonLabel } from "../logic/review-labels";
import "../styles/proposal-review.css";

function Finding({ event, model, disabled }: { event: ReviewEvent; model: ProposalReviewView; disabled: boolean }) {
  const [reason, setReason] = useState(""), [resolution, setResolution] = useState("resolved");
  return <article className="proposal-review__finding"><strong>{event.severity === "blocking" ? "Blokující nález" : event.severity === "warning" ? "Varování" : "Informace"}</strong>
    <p>{event.message}</p><code>{event.anchor || "Celý návrh"}</code><small>{event.by.name} · {event.by.kind === "agent" ? "Tvrzení agenta · nezávisle neověřeno" : "Lokální lidská identita"}</small>
    {model.context?.canResolve && <div className="proposal-review__resolve"><label>Vypořádání nálezu<select value={resolution} disabled={disabled} onChange={e => setResolution(e.target.value)}><option value="resolved">Vyřešeno</option><option value="accepted">Vědomě přijato s odůvodněním</option></select></label>
      <label>Odůvodnění vypořádání<textarea value={reason} maxLength={8000} disabled={disabled} onChange={e => setReason(e.target.value)} /></label>
      <button type="button" disabled={disabled || !reason.trim()} onClick={() => void model.write({ type: "resolve", targetEventId: event.id, resolution, reason })}>Uložit lidské vypořádání</button></div>}
  </article>;
}
function ReviewForm({ model, disabled }: { model: ProposalReviewView; disabled: boolean }) {
  const [type, setType] = useState("comment"), [message, setMessage] = useState(""), [anchor, setAnchor] = useState(""), [severity, setSeverity] = useState("warning");
  return <form className="proposal-review__form" onSubmit={e => { e.preventDefault(); if (!disabled && message.trim()) void model.write({ type, message, anchor, ...(type === "finding" ? { severity } : {}) }); }}>
    <label>Druh připomínky<select value={type} disabled={disabled} onChange={e => setType(e.target.value)}><option value="comment">Komentář</option><option value="finding">Nález</option></select></label>
    {type === "finding" && <label>Závažnost nálezu<select value={severity} disabled={disabled} onChange={e => setSeverity(e.target.value)}><option value="info">Informace</option><option value="warning">Varování</option><option value="blocking">Blokující</option></select></label>}
    <label>Kotva v JSON návrhu<input value={anchor} maxLength={2000} disabled={disabled} onChange={e => setAnchor(e.target.value)} placeholder="/changes/0 nebo prázdné pro celý návrh" /></label>
    <label>Text připomínky<textarea value={message} maxLength={8000} disabled={disabled} onChange={e => setMessage(e.target.value)} /></label>
    <button type="submit" disabled={disabled || !message.trim()}>{model.pending ? "Ukládám…" : "Uložit připomínku k přesnému návrhu"}</button>
  </form>;
}
function RiskAcknowledgement({ model, disabled }: { model: ProposalReviewView; disabled: boolean }) {
  const [confirmed, setConfirmed] = useState(false), value = model.context!;
  return <section className="proposal-review__ack"><h4>Výslovné lidské potvrzení rizika</h4>
    <p>{value.acknowledgementRequired ? "Tato pravidla vyžadují aktuální potvrzení." : "Pro tuto třídu pravidla nevyžadují potvrzení."} Nová událost nebo změna pravidel původní potvrzení zneplatní.</p>
    {value.acknowledgement ? <p>Aktuální uložené potvrzení: <code>{value.acknowledgement.id}</code></p> : <p>Aktuální potvrzení není doloženo.</p>}
    {value.canAcknowledge && <><label><input type="checkbox" checked={confirmed} disabled={disabled} onChange={e => setConfirmed(e.target.checked)} />Rozumím riziku tohoto přesného návrhu, důvodům a aktuální diskusi.</label>
      <button type="button" disabled={disabled || !confirmed || !value.policyHead} onClick={() => { setConfirmed(false); void model.write({ type: "ack", policyId: value.policyHead, riskDigest: value.risk.digest, parentAcceptedHead: value.acceptedHead }); }}>Potvrdit přesné riziko a review</button></>}
  </section>;
}
export default function ProposalReview({ model, proposalId, proposalKind, acceptedHead }: {
  model?: ProposalReviewView; proposalId: string; proposalKind: string; acceptedHead: string | null }) {
  const value = model?.context;
  if (!model || !value || value.proposalId !== proposalId || value.proposalKind !== proposalKind) return <section className="proposal-review" aria-label="Review návrhu"><h3>Review návrhu</h3>
    <p role="status">{model?.busy ? "Načítám přesné review návrhu…" : "Review tohoto návrhu není dostupné. Splnění podmínek není doloženo."}</p>{model?.error && <p role="alert">{model.error}</p>}{model?.actionError && <p role="alert">{model.actionError}</p>}
    {model && <button type="button" disabled={model.pending} onClick={model.refresh}>Obnovit review</button>}</section>;
  const coherent = value.acceptedHead === acceptedHead && !model.busy && !model.error;
  const disabled = !coherent || model.pending || value.readOnly;
  const formKey = JSON.stringify([model.project, model.workspace, proposalKind, proposalId, value.reviewHead, value.policyHead, value.risk.digest, value.acceptedHead]);
  return <section className="proposal-review" aria-label="Review návrhu">
    <header><h3>Review tohoto návrhu</h3><button type="button" disabled={model.pending} onClick={model.refresh}>Obnovit review</button></header>
    <p>Riziko: <strong>{riskLabels[value.risk.level]}</strong> · klasifikováno serverem</p><ul>{value.risk.reasons.map(reason => <li key={reason}>{riskReasonLabel(reason)}</li>)}</ul>
    <p>{value.policy?.enabled ? `Aktivní pravidla přijetí ${value.policyHead}` : "Pravidla přijetí nejsou aktivní. Platí dosavadní lidské přijetí; absence není dokladem review."}</p>
    <p>Jména agentů a lokální session nedokládají nezávislé lidské hlasy. Tato kontrola nepotvrzuje implementaci ani GitHub PR.</p>
    {!coherent && <p role="status">Podklady nemají doloženou společnou přijatou hlavu nebo se obnovují. Přijetí je vypnuté.</p>}
    {value.blockedReasons.length > 0 && <div className="proposal-review__blocked" role="status"><strong>Proč nelze přijmout</strong><ul>{value.blockedReasons.map(reason => <li key={reason}>{blockedReasonLabel(reason)}</li>)}</ul></div>}
    {coherent && !value.blockedReasons.length && <p>Načtené podmínky review neblokují přijetí. Aktuálnost návrhu a jeho zdrojů server znovu ověří při přijetí.</p>}
    {model.actionError && <p role="alert">{model.actionError}</p>}
    <section><h4>Otevřené nálezy ({value.openFindings.length})</h4>{value.openFindings.map(event => <Finding key={`${event.id}:${formKey}`} event={event} model={model} disabled={disabled} />)}
      {!value.openFindings.length && <p>V načtené diskusi nejsou otevřené nálezy; nejde o nezávislé ověření.</p>}</section>
    <RiskAcknowledgement key={`ack:${formKey}`} model={model} disabled={disabled} />
    <ReviewForm key={`form:${formKey}`} model={model} disabled={disabled || !value.canComment} />
    <details><summary>Neměnná historie review ({value.events.length})</summary><ol className="proposal-review__history">{value.events.map(event => <li key={event.id}>
      <strong>{event.type} · {event.by.name}</strong><small>{event.by.kind === "agent" ? "Nahlášeno agentem · neověřeno" : "Lokální lidská identita"} · {new Date(event.createdAt).toLocaleString("cs-CZ")}</small>
      <code>{event.id}</code><p>{event.message ?? event.reason ?? (event.type === "ack" ? `Potvrzení rizika ${event.risk}` : "")}</p>{event.anchor && <code>{event.anchor}</code>}
    </li>)}</ol></details>
    <details><summary>Doklad přijetí a návaznost</summary>{value.receipt ? <><p>Uložený doklad přijetí přesné revize; nepotvrzuje nezávislé hlasy ani implementaci.</p><pre>{JSON.stringify(value.receipt, null, 2)}</pre>
      <a href={`${REVIEW_ROOT}/receipts/${value.acceptedRevision}?${reviewQuery({ project: model.project, workspace: model.workspace })}`} target="_blank" rel="noreferrer">Otevřít přesný JSON dokladu</a></>
      : <p>Doklad přijetí není uložen nebo návrh zatím nebyl přijat. Absence dokladu neznamená provedené review.</p>}</details>
  </section>;
}
