import { useEffect, useRef, useState } from "react";
import { fetchNodeBrief } from "@/shared/desktop-state/logic/api";
import type { NodeBrief } from "@/shared/desktop-state/logic/types";
import { orientationSummary } from "@/editor/node-detail/agent-workspace/logic/agent-orientation";
import { asRecord } from "../logic/handoff";
import type { AgentTaskRequest } from "./context-actions";
import ResultSubmission from "./ResultSubmission";
import "../styles/handoff.css";

export default function TaskHandoff({ request, onClose, onSaved }: { request: AgentTaskRequest; onClose: () => void; onSaved: () => void }) {
  const [brief, setBrief] = useState<NodeBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [clipboardError, setClipboardError] = useState("");
  const [copied, setCopied] = useState(false);
  const [reload, setReload] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const { project, workspace, nodeId } = request;
  // Native modal behavior matches RemovalDialog: the background is inert and Tab stays inside.
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const element = dialog.current!;
    element.showModal();
    close.current?.focus();
    return () => {
      element.close();
      if (opener?.isConnected) opener.focus();
    };
  }, []);
  useEffect(() => {
    let live = true;
    setLoading(true); setError(""); setCopied(false);
    fetchNodeBrief(project, workspace, nodeId)
      .then((value) => { if (live) setBrief(value); })
      .catch((e) => { if (live) setError(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [project, workspace, nodeId, reload]);
  const summary = orientationSummary(brief);
  const json = brief ? JSON.stringify(brief, null, 2) : "";
  const version = typeof brief?.contextVersion === "string" ? brief.contextVersion : "";
  const spec = asRecord(brief?.goal);
  async function copy() {
    try { await navigator.clipboard.writeText(json); setCopied(true); setClipboardError(""); }
    catch { setClipboardError("Schránka není dostupná. Použijte stažení JSON."); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `opora-zadani-${nodeId}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  return <dialog ref={dialog} className="modal handoff" aria-modal="true" aria-label="Předat zadání"
    onCancel={(event) => { event.preventDefault(); onClose(); }}
    onKeyDown={(event) => { if (event.key === "Escape") event.stopPropagation(); }}>
    <button type="button" ref={close} className="close" onClick={onClose} aria-label="Zavřít předání">×</button>
    <h2>Předat zadání · {request.nodeName}</h2>
    <p>Uložené zadání, souvislosti a kontrakt výsledku. Rozepsané neuložené změny se nepředávají.</p>
    <p className="handoff__scope">{project} / {workspace} / {summary.path.join(" / ") || request.nodeName}</p>
    {loading && <p role="status">Načítám uložené zadání…</p>}
    {error && <p role="alert">{error}</p>}
    {clipboardError && <p role="alert">{clipboardError}</p>}
    <button type="button" disabled={loading} onClick={() => setReload((value) => value + 1)}>Načíst aktuální zadání</button>
    {brief && <>
      <h3>Cíl práce</h3><p>{summary.goal || "Cíl práce chybí. Doplňte a uložte zadání v detailu karty."}</p>
      <h3>Podmínky dokončení</h3><p>{typeof spec.acceptance === "string" && spec.acceptance ? spec.acceptance : "Podmínky dokončení nejsou vyplněné."}</p>
      {typeof spec.nonGoals === "string" && spec.nonGoals && <><h3>Co není součástí</h3><p>{spec.nonGoals}</p></>}
      <details><summary>Úplná definice dokončení</summary><pre>{JSON.stringify(summary.definitionOfDone, null, 2)}</pre></details>
      <p>Verze předávaného kontextu: <code className="handoff__version">{version || "nedostupná"}</code></p>
      {summary.gaps.length > 0 && <div className="handoff__gaps"><h3>Co chybí před prací</h3><ul>{summary.gaps.map((gap) => <li key={gap.id}><strong>{gap.label}</strong>: {gap.instruction}</li>)}</ul></div>}
      {request.source !== "canvas" && request.text && <details><summary>Vybraný text pro orientaci</summary><p>{request.text}</p><small>Výběr nemění uložené zadání v předávaném JSON.</small></details>}
      <div className="action-row"><button type="button" disabled={loading || !!error || !version} onClick={() => void copy()}>{copied ? "Zkopírováno" : "Kopírovat celé zadání"}</button><button type="button" disabled={loading || !!error || !version} onClick={download}>Stáhnout JSON pro agenta</button></div>
      <details className="handoff__section"><summary>Přesný předávaný JSON včetně kontraktu výsledku</summary><pre>{json}</pre></details>
      <ResultSubmission brief={brief} project={project} workspace={workspace} nodeId={nodeId} onSaved={onSaved} />
    </>}
  </dialog>;
}
