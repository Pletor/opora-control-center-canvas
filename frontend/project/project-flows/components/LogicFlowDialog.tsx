import { useEffect, useRef, useState } from "react";
import { adoptFlow, createElementFlow, loadLibrary, type LibraryFlowDetail } from "@/project/library-canvas/logic/library-api";
import { libraryChoices, logicFlowTitle, type LibraryChoice } from "../logic/project-flows";
import "../styles/project-flows.css";

type Props = { project: string; workspace: string; node: { id: string; name: string }; onClose: () => void; onCreated: (flowId: string) => void;
  /** Proč nevyšlo založení dvojklikem; okno pak nabídne totéž znovu. */
  error?: string };

/** Malé okno „Nastavit logiku“ u prvku bez plátna: Prázdné plátno, nebo Z knihovny… (plátno s aktivní verzí převezme
 * do projektu jako kopii prvku). Hotové plátno hlásí nahoru; chyba zůstane v okně, Esc a Zrušit zavřou. */
export default function LogicFlowDialog({ project, workspace, node, onClose, onCreated, error: failed = "" }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [choices, setChoices] = useState<LibraryChoice[] | null>(null);
  const [picked, setPicked] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(failed);
  useEffect(() => { const element = dialog.current!; element.showModal(); return () => element.close(); }, []);
  const title = logicFlowTitle(node.name);
  const reason = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));
  async function make(action: () => Promise<LibraryFlowDetail>) {
    setBusy(true); setError("");
    try { onCreated((await action()).id); } catch (cause) { setError(reason(cause)); } finally { setBusy(false); }
  }
  function openLibrary() {
    setError("");
    Promise.all([loadLibrary("human"), loadLibrary("agent")]).then(([human, agent]) => setChoices(libraryChoices([...human, ...agent])), (cause) => setError(reason(cause)));
  }
  return <dialog ref={dialog} className="project-flows-dialog" aria-labelledby="project-flows-dialog-title" data-testid="logic-flow-dialog"
    onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
    <div className="project-flows-dialog__body">
      <h2 id="project-flows-dialog-title" className="project-flows-dialog__title">Nastavit logiku: {title}</h2>
      <p className="project-flows-dialog__hint">Prvek zatím nemá plátno logiky. Na plátně toku se u jednotlivých uzlů nastaví, co se má dít.</p>
      <div className="project-flows-dialog__actions">
        <button type="button" className="project-flows-dialog__primary" disabled={busy} data-testid="logic-flow-empty"
          onClick={() => void make(() => createElementFlow(project, workspace, node.id, title))}>Prázdné plátno</button>
        <button type="button" disabled={busy || choices !== null} data-testid="logic-flow-library" onClick={openLibrary}>Z knihovny…</button>
      </div>
      {choices && (choices.length ? <div className="project-flows-dialog__pick">
        <select aria-label="Plátno z knihovny" value={picked} disabled={busy} data-testid="logic-flow-choice" onChange={(event) => setPicked(event.target.value)}>
          <option value="">Vyberte plátno…</option>
          {choices.map((choice) => <option key={choice.id} value={choice.id}>{choice.folder} · {choice.title}</option>)}
        </select>
        <button type="button" disabled={busy || !picked} data-testid="logic-flow-adopt" onClick={() => void make(() => adoptFlow(picked, project, node.id))}>Převzít</button>
      </div> : <p className="project-flows-dialog__hint">Knihovna nemá plátno s aktivní verzí.</p>)}
      {error && <p className="project-flows-dialog__error" role="alert">{error}</p>}
      <button type="button" className="project-flows-dialog__close" disabled={busy} onClick={onClose}>Zrušit</button>
    </div>
  </dialog>;
}
