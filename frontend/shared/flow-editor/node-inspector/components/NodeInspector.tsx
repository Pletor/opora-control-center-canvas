import { useState } from "react";
import type { FlowNode, FlowNodeDetail, Layer, NodeRun, NodeTypeSpec } from "../../logic/flow-types";
import { formatCost, formatTokens, STATUS_LABEL } from "../../logic/run-overlay";
import { prettyRef } from "../logic/inspector-fields";
import LayerField from "./LayerField";
import ParamFields from "./ParamFields";
import { NodeDataTab, NodeErrorTab, NodeNoteTab } from "./NodeDetailTabs";
import "../styles/node-inspector.css";

type Tab = "params" | "input" | "output" | "data" | "errors" | "note";
const TAB_LABEL: Record<Tab, string> = { params: "Parametry", input: "Vstup", output: "Výstup", data: "Data", errors: "Chyby", note: "Poznámka" };
type Props = {
  node: FlowNode; spec: NodeTypeSpec | undefined; run: NodeRun | null; stall: string | null; readOnly: boolean;
  onParam: (key: string, value: unknown) => void; onRemove: () => void; onClose: () => void;
  /** Pole uzlu plátna toku (data, chyby, poznámka); bez něj inspektor ukazuje běh (Vstup, Výstup). */
  /** Plátno procesů: změna vrstvy uzlu (`undefined` = výchozí z typu); pole se ukáže, jen když typ vrstvu má. */
  onLayer?: (layer: Layer | undefined) => void;
  onField?: <K extends keyof FlowNodeDetail>(key: K, value: FlowNodeDetail[K] | undefined) => void;
};

/** Inspektor uzlu jako postranní panel (ne modál jako NDV v n8n), aby graf zůstal vidět. U běhu tři záložky: Parametry,
 * Vstup a Výstup vybraného běhu, nad nimi stav uzlu v běhu (pokus, model, tokeny, cena, čekání, prostoj a chyba). Plátno
 * toku (`onField`) má záložky Parametry, Data (schémata a příklad), Chyby a Poznámka. */
export default function NodeInspector({ node, spec, run, stall, readOnly, onParam, onRemove, onClose, onField, onLayer }: Props) {
  const [tab, setTab] = useState<Tab>("params");
  const tabs: Tab[] = onField ? ["params", "data", "errors", "note"] : ["params", "input", "output"];
  const ref = tab === "input" ? run?.input_ref : run?.output_ref;
  return <aside className="node-inspector" aria-label={`Uzel ${node.id}`} data-testid="node-inspector">
    <header className="node-inspector__head">
      <span className="node-inspector__title"><b>{node.id}</b><small className="node-inspector__muted">{node.type} · v{node.type_version ?? spec?.version ?? 1}</small></span>
      <button type="button" className="node-inspector__close" aria-label="Zavřít inspektor" onClick={onClose}>×</button>
    </header>
    {onLayer && spec && <LayerField value={node.layer} typeLayer={spec.layer} readOnly={readOnly} onLayer={onLayer}/>}
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
    <nav className={`node-inspector__tabs node-inspector__tabs--${tabs.length}`} aria-label="Záložky inspektoru">
      {tabs.map((id) => <button key={id} type="button" className="node-inspector__tab" aria-pressed={tab === id} data-testid={`node-inspector-tab-${id}`}
        onClick={() => setTab(id)}>{TAB_LABEL[id]}</button>)}
    </nav>
    {tab === "params" ? <ParamFields key={node.id} params={node.params} hints={spec?.params} readOnly={readOnly} onParam={onParam}/>
      : onField && tab === "data" ? <NodeDataTab node={node} readOnly={readOnly} onField={onField}/>
      : onField && tab === "errors" ? <NodeErrorTab node={node} readOnly={readOnly} onField={onField}/>
      : onField && tab === "note" ? <NodeNoteTab node={node} readOnly={readOnly} onField={onField}/>
      : run ? <pre className="node-inspector__data">{prettyRef(ref) || "— bez dat —"}</pre>
        : <p className="node-inspector__muted">Vyberte běh, ve kterém uzel proběhl.</p>}
    {node.pinned_output !== undefined && node.pinned_output !== null && <p className="node-inspector__muted">Připnutý výstup: uzel se v běhu nevykoná.</p>}
    {!readOnly && <button type="button" className="node-inspector__remove" onClick={onRemove}>Smazat uzel</button>}
  </aside>;
}
