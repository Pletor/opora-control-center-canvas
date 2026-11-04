import { useContext, useState } from "react";
import { NodeResizer, type NodeProps } from "@xyflow/react";
import type { FlowNoteNode } from "../../logic/frame-view";
import { FrameActionsContext, NOTE_COLORS } from "../logic/frame-actions";
import { noteBlocks, type NoteInline } from "../logic/note-markdown";
import "../styles/flow-frame.css";

function Inline({ parts }: { parts: NoteInline[] }) {
  return <>{parts.map((part, index) => part.code ? <code key={index}>{part.text}</code> : part.strong ? <b key={index}>{part.text}</b> : <span key={index}>{part.text}</span>)}</>;
}

/** Sticky poznámka za uzly (n8n sticky note): markdown, sedm barev, tah za plochu a změna velikosti za okraj. Dvojklik
 * otevře úpravu textu, opuštění pole ji uloží. Vybraná poznámka nabídne barvy. Jen ke čtení se nehýbe ani nemění. */
export default function FlowNoteCard({ data, selected }: NodeProps<FlowNoteNode>) {
  const { note, readOnly } = data;
  const { onNote } = useContext(FrameActionsContext);
  const [draft, setDraft] = useState<string | null>(null);
  const commit = () => { if (draft !== null && draft !== note.content) onNote(note.id, { content: draft }); setDraft(null); };
  return <div className={`flow-frame__note flow-frame__note--c${note.color ?? 1}`} data-testid={`flow-note-${note.id}`}
    onDoubleClick={() => { if (!readOnly) setDraft(note.content); }}>
    <NodeResizer isVisible={selected && !readOnly} minWidth={80} minHeight={60} lineClassName="flow-frame__resize" handleClassName="flow-frame__handle"
      onResizeEnd={(_, size) => onNote(note.id, size)}/>
    {draft !== null
      ? <textarea className="flow-frame__note-edit nodrag nowheel" autoFocus aria-label="Text poznámky (markdown)" value={draft}
        onChange={(event) => setDraft(event.target.value)} onBlur={commit} onKeyDown={(event) => { if (event.key === "Escape") setDraft(null); }}/>
      : <div className="flow-frame__note-text">{noteBlocks(note.content).map((block, index) => block.kind === "heading"
        ? <p key={index} className={`flow-frame__note-h flow-frame__note-h--${block.level}`}><Inline parts={block.inline}/></p>
        : <p key={index} className={block.kind === "item" ? "flow-frame__note-item" : "flow-frame__note-p"}><Inline parts={block.inline}/></p>)}</div>}
    {selected && !readOnly && draft === null && <div className="flow-frame__colors nodrag" role="group" aria-label="Barva poznámky">
      {NOTE_COLORS.map((color) => <button key={color} type="button" className={`flow-frame__color flow-frame__note--c${color}`} aria-label={`Barva ${color}`}
        aria-pressed={(note.color ?? 1) === color} onClick={() => onNote(note.id, { color })}/>)}
    </div>}
  </div>;
}
