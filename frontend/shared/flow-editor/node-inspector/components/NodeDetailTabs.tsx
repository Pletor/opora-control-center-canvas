import { useState } from "react";
import type { FlowNode, FlowNodeDetail } from "../../logic/flow-types";
import { parseRetry } from "../logic/node-fields";
import JsonField from "./JsonField";

type OnField = <K extends keyof FlowNodeDetail>(key: K, value: FlowNodeDetail[K] | undefined) => void;
type Props = { node: FlowNode; readOnly: boolean; onField: OnField };

/** Záložka Data: schéma vstupu, schéma výstupu a ukázková data (obdoba pinData n8n) jako JSON editory. */
export function NodeDataTab({ node, readOnly, onField }: Props) {
  return <div className="node-inspector__fields" data-testid="node-inspector-data">
    <p className="node-inspector__muted">Po hlavní vazbě teče seznam položek {"{json, binary?, pairedItem?}"}; uzel běží pro každou položku, s režimem „jednou“ jen jednou.</p>
    <JsonField label="Vstup" hint="inputSchema · JSON Schema nebo příklad" value={node.inputSchema} object readOnly={readOnly} onCommit={(value) => onField("inputSchema", value as FlowNodeDetail["inputSchema"])}/>
    <JsonField label="Výstup" hint="outputSchema · JSON Schema nebo příklad" value={node.outputSchema} object readOnly={readOnly} onCommit={(value) => onField("outputSchema", value as FlowNodeDetail["outputSchema"])}/>
    <JsonField label="Příklad" hint="example · ukázková data" value={node.example} object={false} readOnly={readOnly} onCommit={(value) => onField("example", value)}/>
  </div>;
}

/** Záložka Chyby: co se stane při chybě (zastavit, pokračovat, chybový výstup `error`), opakování a režim běhu. */
export function NodeErrorTab({ node, readOnly, onField }: Props) {
  const [tries, setTries] = useState(String(node.retry?.maxTries ?? "")), [wait, setWait] = useState(String(node.retry?.waitMs ?? "")), [error, setError] = useState("");
  const commit = () => { const parsed = parseRetry(tries, wait); if ("error" in parsed) setError(parsed.error); else { setError(""); onField("retry", parsed.value as FlowNodeDetail["retry"]); } };
  return <div className="node-inspector__fields" data-testid="node-inspector-errors">
    <label className="node-inspector__field node-inspector__field--block"><span className="node-inspector__key">Při chybě<small className="node-inspector__kind">onError</small></span>
      <select className="node-inspector__input" disabled={readOnly} value={node.onError ?? "stop"} onChange={(event) => onField("onError", event.target.value === "stop" ? undefined : event.target.value as FlowNodeDetail["onError"])}>
        <option value="stop">Zastavit tok</option><option value="continue">Pokračovat s posledními platnými daty</option><option value="errorOutput">Pokračovat chybovým výstupem „error“</option>
      </select></label>
    <div className="node-inspector__pair">
      <label className="node-inspector__field node-inspector__field--block"><span className="node-inspector__key">Pokusů<small className="node-inspector__kind">retry.maxTries</small></span>
        <input className="node-inspector__input" inputMode="numeric" readOnly={readOnly} value={tries} placeholder="bez opakování" onChange={(event) => setTries(event.target.value)} onBlur={commit}/></label>
      <label className="node-inspector__field node-inspector__field--block"><span className="node-inspector__key">Čekat ms<small className="node-inspector__kind">retry.waitMs</small></span>
        <input className="node-inspector__input" inputMode="numeric" readOnly={readOnly} value={wait} placeholder="0" onChange={(event) => setWait(event.target.value)} onBlur={commit}/></label>
    </div>
    {error && <span className="node-inspector__error" role="alert">{error}</span>}
    <label className="node-inspector__field node-inspector__field--block"><span className="node-inspector__key">Režim<small className="node-inspector__kind">mode</small></span>
      <select className="node-inspector__input" disabled={readOnly} value={node.mode ?? "perItem"} onChange={(event) => onField("mode", event.target.value === "perItem" ? undefined : "once")}>
        <option value="perItem">Pro každou položku</option><option value="once">Jednou pro všechny položky</option>
      </select></label>
  </div>;
}

/** Záložka Poznámka: text poznámky a „ukázat v toku“ (podtitulek na kartě, n8n Display note in flow). */
export function NodeNoteTab({ node, readOnly, onField }: Props) {
  const [notes, setNotes] = useState(node.notes ?? "");
  return <div className="node-inspector__fields" data-testid="node-inspector-note">
    <label className="node-inspector__field node-inspector__field--block"><span className="node-inspector__key">Poznámka<small className="node-inspector__kind">notes</small></span>
      <textarea className="node-inspector__input" readOnly={readOnly} rows={5} value={notes} onChange={(event) => setNotes(event.target.value)}
        onBlur={() => { if (notes !== (node.notes ?? "")) onField("notes", notes || undefined); }}/></label>
    <label className="node-inspector__check"><input type="checkbox" disabled={readOnly} checked={!!node.notesInFlow} onChange={(event) => onField("notesInFlow", event.target.checked || undefined)}/>
      Ukázat poznámku na kartě jako podtitulek</label>
  </div>;
}
