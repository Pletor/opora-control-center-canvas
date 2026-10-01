import { useEffect, useRef, useState } from "react";
import { cleanTitle, type TaskView } from "../logic/task-overview";

/**
 * Jeden úkol v přehledu: název, stav tečkou a slovem, model, čas a náhled poslední odpovědi.
 * Dvojklik nebo tužka otevře přejmenování v řádku (Enter uloží, Esc zruší), křížek se zeptá
 * přímo v řádku, jestli úkol opravdu zavřít. Všechno hlásí nahoru; nic sám neukládá.
 */
export default function TaskItem({
  task,
  onSelect,
  onRename,
  onClose,
}: {
  task: TaskView;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => Promise<boolean>;
  onClose: (id: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(task.title);
  const [confirming, setConfirming] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const cancelled = useRef(false);
  useEffect(() => { if (editing) input.current?.select(); }, [editing]);

  function startRename() {
    setValue(task.title);
    setConfirming(false);
    cancelled.current = false;
    setEditing(true);
  }
  async function commit() {
    if (cancelled.current) return;
    const title = cleanTitle(value);
    cancelled.current = true; // Enter a následný blur nesmí přejmenovat dvakrát.
    if (!title || title === task.title) { setEditing(false); return; }
    if (await onRename(task.id, title)) setEditing(false);
    else cancelled.current = false;
  }

  const className = "assistant-panel__task" + (task.active ? " assistant-panel__task--active" : "") + (task.isNew ? " assistant-panel__task--new" : "");
  if (confirming) {
    return (
      <li className={className}>
        <div className="assistant-panel__task-confirm" role="group" aria-label={`Zavřít úkol ${task.title}`}>
          <span className="assistant-panel__task-question">Zavřít úkol „{task.title}“?</span>
          <span className="assistant-panel__task-answers">
            <button type="button" className="assistant-panel__task-answer assistant-panel__task-answer--danger" onClick={() => onClose(task.id)}>Zavřít</button>
            <button type="button" className="assistant-panel__task-answer" autoFocus onClick={() => setConfirming(false)}>Nechat</button>
          </span>
        </div>
      </li>
    );
  }
  return (
    <li className={className}>
      {editing ? (
        <input
          ref={input}
          className="assistant-panel__task-rename"
          aria-label="Nový název úkolu"
          maxLength={80}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={() => void commit()}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); void commit(); }
            if (e.key === "Escape") { e.preventDefault(); cancelled.current = true; setEditing(false); }
          }}
        />
      ) : (
        <button
          type="button"
          className="assistant-panel__task-open"
          aria-current={task.active ? "true" : undefined}
          onClick={() => onSelect(task.id)}
          onDoubleClick={startRename}
        >
          <span className="assistant-panel__task-title">{task.title}</span>
          <span className="assistant-panel__task-meta">
            <span className={`assistant-panel__status assistant-panel__status--${task.status}`}>
              <span className="assistant-panel__status-dot" aria-hidden="true" />
              {task.statusWord}
            </span>
            {task.isNew && <span className="assistant-panel__task-new">nové</span>}
            <span className="assistant-panel__task-model">{task.model}</span>
            <span className="assistant-panel__task-when">{task.when}</span>
          </span>
          {task.preview && <span className="assistant-panel__task-preview">{task.preview}</span>}
        </button>
      )}
      {!editing && (
        <span className="assistant-panel__task-tools">
          <button type="button" className="assistant-panel__task-tool" aria-label="Přejmenovat úkol" title="Přejmenovat (dvojklik)" onClick={startRename}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M4 20h4L19 9l-4-4L4 16v4Z" />
            </svg>
          </button>
          <button type="button" className="assistant-panel__task-tool" aria-label="Zavřít úkol" title="Zavřít úkol" onClick={() => setConfirming(true)}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </button>
        </span>
      )}
    </li>
  );
}
