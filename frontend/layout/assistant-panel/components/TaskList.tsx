import { MODELS, type AssistantModel } from "../logic/assistant-api";
import { tasksCount, type TaskView } from "../logic/task-overview";
import TaskItem from "./TaskItem";

/**
 * Přehled úkolů. Na celé ploše je to trvalý sloupec vlevo (`column`), v panelu vpravo rozbalovací
 * pruh nahoře (`drawer`): sbalený ukazuje aktivní úkol a počet, rozbalený celý seznam. Nahoře je vždy
 * „+ Nový úkol“ s výběrem modelu. Dílek jen zobrazuje a hlásí volby nahoru.
 */
export default function TaskList({
  variant,
  tasks,
  expanded,
  model,
  onToggle,
  onModel,
  onCreate,
  onSelect,
  onRename,
  onClose,
}: {
  variant: "column" | "drawer";
  tasks: TaskView[];
  expanded: boolean;
  model: AssistantModel;
  onToggle: () => void;
  onModel: (model: AssistantModel) => void;
  onCreate: () => void;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => Promise<boolean>;
  onClose: (id: string) => void;
}) {
  const active = tasks.find((t) => t.active) ?? null;
  const others = tasks.filter((t) => !t.active && (t.isNew || t.status === "working" || t.status === "waiting")).length;
  const open = variant === "column" || expanded;
  return (
    <nav className={`assistant-panel__tasks assistant-panel__tasks--${variant}`} aria-label="Úkoly asistenta">
      {variant === "drawer" && (
        <button type="button" className="assistant-panel__tasks-toggle" aria-expanded={expanded} onClick={onToggle}>
          {active ? (
            <span className="assistant-panel__tasks-current">
              <span className={`assistant-panel__status assistant-panel__status--${active.status}`} title={active.statusWord}>
                <span className="assistant-panel__status-dot" aria-hidden="true" />
              </span>
              <span className="assistant-panel__tasks-current-title">{active.title}</span>
            </span>
          ) : (
            <span className="assistant-panel__tasks-current">Žádný úkol</span>
          )}
          <span className="assistant-panel__tasks-count">
            {tasksCount(tasks.length)}
            {others > 0 && !expanded && <span className="assistant-panel__tasks-badge" title="Jiný úkol pracuje nebo má novou odpověď" />}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" className="assistant-panel__tasks-chevron">
              <path d="m6 9 6 6 6-6" />
            </svg>
          </span>
        </button>
      )}
      {open && (
        <div className="assistant-panel__tasks-body">
          <div className="assistant-panel__tasks-head">
            {variant === "column" && <span className="assistant-panel__tasks-title" title="Alt+↑ / Alt+↓ přepíná úkoly">Úkoly <span className="assistant-panel__tasks-total">{tasks.length}</span></span>}
            <span className="assistant-panel__new">
              <select className="assistant-panel__model" aria-label="Model nového úkolu" title="Model nového úkolu" value={model} onChange={(e) => onModel(e.target.value as AssistantModel)}>
                {MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
              <button type="button" className="assistant-panel__new-task" onClick={onCreate}>+ Nový úkol</button>
            </span>
          </div>
          {tasks.length > 0 && (
            <ul className="assistant-panel__task-list">
              {tasks.map((t) => <TaskItem key={t.id} task={t} onSelect={onSelect} onRename={onRename} onClose={onClose} />)}
            </ul>
          )}
        </div>
      )}
    </nav>
  );
}
