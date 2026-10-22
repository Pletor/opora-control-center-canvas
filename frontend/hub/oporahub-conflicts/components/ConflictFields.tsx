import { useState } from "react";
import { api, ApiError } from "@/shared/types/logic/types";
import { fieldRows, resolutionDraft, resolveError, resolveUrl, validProposalId, type Choices, type Conflict, type Side } from "../logic/conflicts";

/** Jeden konflikt: pole po řádcích (base | ours | theirs), volba strany, návrh řešení a připojení nového návrhu. */
export default function ConflictFields({ conflict, project, workspace, onResolved }: {
  conflict: Conflict; project: string; workspace: string; onResolved: () => void;
}) {
  const [choices, setChoices] = useState<Choices>({});
  const [proposal, setProposal] = useState("");
  const [state, setState] = useState({ busy: false, error: "", done: "" });
  const rows = fieldRows(conflict, choices);
  const draft = resolutionDraft(conflict, choices);
  const open = conflict.status === "open";
  const choose = (key: string, side: Side) => setChoices(current => ({ ...current, [key]: side }));
  async function copy() {
    try { await navigator.clipboard.writeText(draft.text); setState(current => ({ ...current, done: "Návrh řešení zkopírován." })); }
    catch { setState(current => ({ ...current, error: "Schránka není dostupná; text označte a zkopírujte ručně." })); }
  }
  async function resolve() {
    if (!validProposalId(proposal)) { setState({ busy: false, error: "Zadejte ID nového návrhu (písmena, číslice, _ . : -).", done: "" }); return; }
    setState({ busy: true, error: "", done: "" });
    try {
      await api(resolveUrl(conflict.id), { project, workspace, resolutionProposalId: proposal.trim() });
      setState({ busy: false, error: "", done: "Řešení připojeno; konflikt je vyřešený." }); onResolved();
    } catch (error) {
      setState({ busy: false, done: "", error: resolveError(error instanceof ApiError ? error.status : undefined, error instanceof Error ? error.message : "") });
    }
  }
  return <section className="oporahub-conflicts__detail" aria-label={`Konflikt ${conflict.id}`} data-oh-conflict={conflict.id} data-oh-conflict-status={conflict.status}>
    <div className="oporahub-conflicts__table" role="table" aria-label="Pole konfliktu">
      <div className="oporahub-conflicts__row oporahub-conflicts__row--head" role="row">
        {["pole", "base · přijato u rodiče", "ours · návrh", "theirs · aktuální hlava"].map(name => <span key={name} role="columnheader">{name}</span>)}
      </div>
      {rows.map(row => <div key={row.key} role="row" className="oporahub-conflicts__row" data-oh-field-key={row.key} data-oh-choice={row.choice}>
        <code role="cell" className="oporahub-conflicts__key">{row.key}</code>
        <span role="cell" className="oporahub-conflicts__value">{row.base}</span>
        {(["ours", "theirs"] as const).map(side => <label key={side} role="cell"
          className={`oporahub-conflicts__value${(side === "ours" ? row.oursChanged : row.theirsChanged) ? " oporahub-conflicts__value--changed" : ""}${row.choice === side ? " oporahub-conflicts__value--chosen" : ""}`}>
          {open && <input type="radio" name={`${conflict.id}:${row.key}`} checked={row.choice === side} onChange={() => choose(row.key, side)}
            aria-label={`${row.key}: ${side === "ours" ? "ponechat návrh" : "ponechat hlavu"}`} />}
          <span>{side === "ours" ? row.ours : row.theirs}</span>
        </label>)}
      </div>)}
    </div>
    {open ? <div className="oporahub-conflicts__resolve">
      <h3 className="oporahub-conflicts__title">Návrh řešení {draft.complete ? "✓ úplný" : "◷ rozhodněte všechna pole"}</h3>
      <pre className="oporahub-conflicts__draft">{draft.text}</pre>
      <button type="button" className="oporahub-conflicts__button" onClick={() => void copy()}>Kopírovat návrh řešení</button>
      <p className="oporahub-conflicts__note">1. Podle návrhu založte běžný nový návrh nad aktuální hlavou (formuláře zadání, grafu nebo obsahu).
        2. Jeho ID připojte sem. Server ověří, že jde o jiný návrh s rodičem rovným aktuální hlavě.</p>
      <label className="oporahub-conflicts__field">ID nového návrhu
        <input value={proposal} onChange={event => setProposal(event.target.value)} placeholder="např. cs_…" spellCheck={false} />
      </label>
      <button type="button" className="oporahub-conflicts__button oporahub-conflicts__button--primary" disabled={state.busy || !proposal.trim()}
        onClick={() => void resolve()}>{state.busy ? "Připojuji…" : "Připojit řešení"}</button>
    </div> : <p className="oporahub-conflicts__note">Konflikt je {conflict.status === "resolved" ? `vyřešený návrhem ${conflict.resolutionProposalId ?? "?"}` : "zastaralý (hlava se posunula nebo návrh byl převeden)"}.</p>}
    {state.error && <p className="oporahub-conflicts__warning" role="alert">✕ {state.error}</p>}
    {state.done && <p className="oporahub-conflicts__note" role="status">✓ {state.done}</p>}
  </section>;
}
