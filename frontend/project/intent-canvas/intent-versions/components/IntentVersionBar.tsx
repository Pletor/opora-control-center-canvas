import { useState } from "react";
import type { FlowVersion } from "@/shared/flow-editor/logic/flow-types";
import type { IntentLane } from "../logic/intent-versions";
import "../styles/intent-versions.css";

type Props = {
  lane: IntentLane; viewingId: string | null; diffText: string; dirty: boolean; busy: boolean;
  onView: (id: string) => void; onSaveDraft: () => void; onDiscard: () => void; onPropose: () => void;
  onApprove: () => void; onReject: (reason: string) => void;
};
const SLOTS = [["active", "aktivní"], ["candidate", "kandidát"], ["draft", "draft"]] as const;

/** Lišta verzí záměru: aktivní, kandidát a rozpracovaný draft, rozdíl zobrazené verze proti aktivní a akce. Úprava jde
 * uložit jen jako nový draft, draft jde navrhnout ke schválení a kandidáta schválí nebo zamítne (s důvodem) jen člověk. */
export default function IntentVersionBar({ lane, viewingId, diffText, dirty, busy, onView, onSaveDraft, onDiscard, onPropose, onApprove, onReject }: Props) {
  const [reason, setReason] = useState<string | null>(null);
  const viewing = [lane.active, lane.candidate, lane.draft].find((item) => item?.id === viewingId) ?? null;
  const decide = !dirty && viewing?.status === "candidate";
  const chip = (version: FlowVersion | null, status: string, label: string) => version
    ? <button key={status} type="button" disabled={busy} aria-pressed={version.id === viewingId} onClick={() => onView(version.id)}
      className={`intent-versions__chip intent-versions__chip--${status}${version.id === viewingId ? " intent-versions__chip--current" : ""}`}>
      v{version.n}<small className="intent-versions__status">{label}</small></button>
    : <span key={status} className="intent-versions__chip intent-versions__chip--empty">—<small className="intent-versions__status">{label}</small></span>;
  return <div className="intent-versions" data-testid="intent-versions">
    <div className="intent-versions__chips" role="group" aria-label="Verze záměru">{SLOTS.filter(([slot]) => slot !== "draft" || lane.draft).map(([slot, label]) => chip(lane[slot], slot, label))}</div>
    {diffText && <span className="intent-versions__diff" data-testid="intent-diff" title="Uzly zobrazené verze proti aktivní">proti aktivní: {diffText}</span>}
    <span className="intent-versions__actions">
      {dirty && <>
        <span className="intent-versions__dirty">neuložená úprava</span>
        <button type="button" className="intent-versions__button intent-versions__button--primary" disabled={busy} onClick={onSaveDraft}>Uložit draft</button>
        <button type="button" className="intent-versions__button" disabled={busy} onClick={onDiscard}>Zahodit</button>
      </>}
      {!dirty && viewing?.status === "draft" && <button type="button" className="intent-versions__button" disabled={busy} onClick={onPropose}>Navrhnout ke schválení</button>}
      {decide && reason === null && <>
        <button type="button" className="intent-versions__button intent-versions__button--approve" disabled={busy} onClick={onApprove}>Schválit</button>
        <button type="button" className="intent-versions__button intent-versions__button--reject" disabled={busy} onClick={() => setReason("")}>Zamítnout</button>
      </>}
      {decide && reason !== null && <form className="intent-versions__reject" onSubmit={(event) => { event.preventDefault(); if (reason.trim()) { onReject(reason); setReason(null); } }}>
        <input className="intent-versions__reason" autoFocus required maxLength={2000} placeholder="Proč kandidáta zamítáte?" aria-label="Důvod zamítnutí"
          value={reason} onChange={(event) => setReason(event.target.value)}/>
        <button type="submit" className="intent-versions__button intent-versions__button--reject" disabled={busy || !reason.trim()}>Zamítnout</button>
        <button type="button" className="intent-versions__button" onClick={() => setReason(null)}>Zpět</button>
      </form>}
    </span>
  </div>;
}
