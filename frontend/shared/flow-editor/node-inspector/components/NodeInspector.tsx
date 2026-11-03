import { useState } from "react";
import type { FlowNode, NodeRun, NodeTypeSpec } from "../../logic/flow-types";
import { formatCost, formatTokens, STATUS_LABEL } from "../../logic/run-overlay";
import { prettyRef } from "../logic/inspector-fields";
import ParamFields from "./ParamFields";
import "../styles/node-inspector.css";

type Tab = "params" | "input" | "output";
type Props = {
  node: FlowNode; spec: NodeTypeSpec | undefined; run: NodeRun | null; stall: string | null; readOnly: boolean;
  onParam: (key: string, value: unknown) => void; onRemove: () => void; onClose: () => void;
};

/** Inspektor uzlu jako postranní panel (ne modál jako NDV v n8n), aby graf zůstal vidět. Tři záložky: Parametry,
 * Vstup a Výstup vybraného běhu. Nad nimi stav uzlu v běhu: pokus, model, tokeny, cena, čekání, prostoj a chyba. */
export default function NodeInspector({ node, spec, run, stall, readOnly, onParam, onRemove, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("params");
  const ref = tab === "input" ? run?.input_ref : run?.output_ref;
  return <aside className="node-inspector" aria-label={`Uzel ${node.id}`} data-testid="node-inspector">
    <header className="node-inspector__head">
      <span className="node-inspector__title"><b>{node.id}</b><small className="node-inspector__muted">{node.type} · v{node.type_version ?? spec?.version ?? 1}</small></span>
      <button type="button" className="node-inspector__close" aria-label="Zavřít inspektor" onClick={onClose}>×</button>
    </header>
    {!spec && <p className="node-inspector__error">Typ uzlu není v registru.</p>}
    {run && <dl className="node-inspector__run">
      <dt className="node-inspector__term">Stav</dt><dd className={`node-inspector__status node-inspector__status--${run.status}`}>{STATUS_LABEL[run.status]} · pokus {run.attempt}</dd>
      {run.model && <><dt className="node-inspector__term">Model</dt><dd className="node-inspector__value">{run.provider ? `${run.provider} · ` : ""}{run.model}</dd></>}
      {(run.tokens_in || run.tokens_out) ? <><dt className="node-inspector__term">Tokeny</dt><dd className="node-inspector__value">{formatTokens((run.tokens_in ?? 0) + (run.tokens_out ?? 0))}</dd></> : null}
      {run.cost_usd ? <><dt className="node-inspector__term">Cena</dt><dd className="node-inspector__value">{formatCost(run.cost_usd)}</dd></> : null}
      {run.waiting_for && <><dt className="node-inspector__term">Čeká na</dt><dd className="node-inspector__value">{run.waiting_for}{run.deadline ? ` do ${new Date(run.deadline).toLocaleString("cs-CZ")}` : ""}</dd></>}
      {stall && <><dt className="node-inspector__term">Prostoj</dt><dd className="node-inspector__value node-inspector__stall">{stall}</dd></>}
      {run.error && <><dt className="node-inspector__term">Chyba</dt><dd className="node-inspector__value node-inspector__error">{run.error}</dd></>}
    </dl>}
    <nav className="node-inspector__tabs" aria-label="Záložky inspektoru">
      {(["params", "input", "output"] as const).map((id) => <button key={id} type="button" className="node-inspector__tab" aria-pressed={tab === id}
        onClick={() => setTab(id)}>{id === "params" ? "Parametry" : id === "input" ? "Vstup" : "Výstup"}</button>)}
    </nav>
    {tab === "params"
      ? <ParamFields key={node.id} params={node.params} readOnly={readOnly} onParam={onParam}/>
      : run ? <pre className="node-inspector__data">{prettyRef(ref) || "— bez dat —"}</pre>
        : <p className="node-inspector__muted">Vyberte běh, ve kterém uzel proběhl.</p>}
    {node.pinned_output !== undefined && node.pinned_output !== null && <p className="node-inspector__muted">Připnutý výstup: uzel se v běhu nevykoná.</p>}
    {!readOnly && <button type="button" className="node-inspector__remove" onClick={onRemove}>Smazat uzel</button>}
  </aside>;
}
