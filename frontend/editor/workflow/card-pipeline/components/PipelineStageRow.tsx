// Řádek etapy pipeline: druh, název, pohled kritika, stav (hlásí ho relace agenta) a zásahy člověka.
// Klik na název rozbalí zadání a předávku etapy; přeskočit / vrátit je jeden klik. Změny bublají nahoru.
import { useState } from "react";
import { KIND_ICON, KIND_LABEL, LENS_LABEL, STATUS_LABEL, type PipelineStage } from "@/editor/workflow/card-pipeline/logic/pipeline-model";

export default function PipelineStageRow({
  stage, first, current, disabled, onMove, onRemove, onSkip, onEdit,
}: {
  stage: PipelineStage;
  first: boolean;
  current: boolean;
  disabled: boolean;
  onMove: (delta: number) => void;
  onRemove: () => void;
  onSkip: () => void;
  onEdit: (title: string, brief: string) => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(stage.title);
  const [brief, setBrief] = useState(stage.brief);
  const finished = stage.status === "passed" || stage.status === "failed";
  return (
    <li className={`pipeline-stage pipeline-stage--${stage.status}` + (current ? " pipeline-stage--current" : "")}>
      <div className="pipeline-stage__row">
        <span className={`pipeline-kind pipeline-kind--${stage.kind}`} title={KIND_LABEL[stage.kind]}>{KIND_ICON[stage.kind]}</span>
        <button type="button" className="pipeline-stage__title" aria-expanded={open} onClick={() => setOpen(!open)}>
          {stage.title}
          {stage.lens && <span className={`pipeline-lens pipeline-lens--${stage.lens}`}>{LENS_LABEL[stage.lens]}</span>}
          {stage.retryOf && <span className="pipeline-retry" title="Opakování po opravě; vložil ho server">↺</span>}
        </button>
        <span className={`pipeline-status pipeline-status--${stage.status}`}>{current ? "na řadě" : STATUS_LABEL[stage.status]}</span>
        <span className="block-tools">
          <button type="button" aria-label={stage.status === "skipped" ? "Vrátit etapu" : "Přeskočit etapu"} title={stage.status === "skipped" ? "Vrátit" : "Přeskočit (jen člověk)"}
            disabled={disabled || finished} onClick={onSkip}>{stage.status === "skipped" ? "↩" : "⤼"}</button>
          <button type="button" aria-label="Posunout výš" disabled={disabled || first} onClick={() => onMove(-1)}>▲</button>
          <button type="button" aria-label="Odebrat etapu" disabled={disabled} onClick={onRemove}>✕</button>
        </span>
      </div>
      {(stage.note || stage.doneBy) && (
        <p className="pipeline-stage__note">{stage.doneBy && <b>{stage.doneBy}: </b>}{stage.note}</p>
      )}
      {open && (
        <div className="pipeline-stage__edit">
          <input aria-label="Název etapy" value={title} disabled={disabled} onChange={(e) => setTitle(e.target.value)} />
          <textarea aria-label="Zadání etapy" rows={3} value={brief} disabled={disabled} placeholder="Co má etapa ověřit a podle čeho pozná hotovo" onChange={(e) => setBrief(e.target.value)} />
          <button type="button" className="block-add" disabled={disabled || !title.trim() || (title === stage.title && brief === stage.brief)}
            onClick={() => onEdit(title.trim(), brief).then((ok) => { if (ok) setOpen(false); })}>Uložit etapu</button>
        </div>
      )}
    </li>
  );
}
