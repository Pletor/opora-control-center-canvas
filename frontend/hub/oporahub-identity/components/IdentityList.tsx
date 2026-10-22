import { useState } from "react";
import { ToneChip } from "@/hub/oporahub-health/components/HealthMark";
import { evidenceUrl, stateView, type Identity } from "../logic/identities";

const when = (value: string | null) => {
  const time = value ? Date.parse(value) : NaN;
  return Number.isFinite(time) ? new Date(time).toLocaleString("cs-CZ") : "—";
};

/** Seznam lidí: stav (značka + slovo + tón), operátor, login, kdy ověřeno a důkaz; zrušení s potvrzením v řádku. */
export default function IdentityList({ items, busy, onRevoke }: { items: Identity[]; busy: boolean; onRevoke: (identityId: string) => Promise<boolean> }) {
  const [confirming, setConfirming] = useState("");
  return <section className="oporahub-identity__panel" aria-labelledby="oh-identity-list">
    <h4 id="oh-identity-list" className="oporahub-identity__subtitle">Registr · {items.filter(item => item.state === "verified").length} ověřených</h4>
    <div className="oporahub-identity__table" role="table" aria-label="Lidské identity">
      <div role="row" className="oporahub-identity__row oporahub-identity__row--head">
        {["člověk", "GitHub", "stav", "ověřeno", "důkaz", ""].map((label, index) => <span key={index} role="columnheader">{label}</span>)}
      </div>
      {items.map(item => {
        const state = stateView[item.state], url = evidenceUrl(item);
        return <div key={item.identityId} role="row" className="oporahub-identity__row" data-oh-identity={item.identityId}
          data-oh-identity-state={item.state} data-oh-operator={String(item.operator)} data-oh-github-login={item.githubLogin}>
          <span role="cell"><b>{item.name}</b>{item.operator && <> <ToneChip tone="acc">operátor</ToneChip></>}</span>
          <span role="cell" className="oporahub-identity__mono">@{item.githubLogin}</span>
          <span role="cell"><ToneChip tone={state.tone}>{state.glyph} {state.label}</ToneChip></span>
          <span role="cell" className="oporahub-identity__mono">{when(item.verifiedAt)}</span>
          <span role="cell">{url ? <a href={url} target="_blank" rel="noreferrer noopener">komentář</a> : "—"}</span>
          <span role="cell">{item.state !== "revoked" && (confirming === item.identityId
            ? <span className="oporahub-identity__confirm">Opravdu zrušit?
                <button type="button" className="oporahub-identity__button oporahub-identity__button--danger" disabled={busy}
                  onClick={() => void onRevoke(item.identityId).then(() => setConfirming(""))}>Zrušit identitu</button>
                <button type="button" className="oporahub-identity__button" onClick={() => setConfirming("")}>Ponechat</button></span>
            : <button type="button" className="oporahub-identity__button" disabled={busy} onClick={() => setConfirming(item.identityId)}>Zrušit…</button>)}</span>
        </div>;
      })}
      {!items.length && <p className="oporahub-identity__note oporahub-identity__empty">{busy ? "Načítám registr…" : "Zatím žádná identita. Brána počítá účty jako dosud."}</p>}
    </div>
  </section>;
}
