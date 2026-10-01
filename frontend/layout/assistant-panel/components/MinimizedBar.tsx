import type { Ref } from "react";
import { tasksCount, type TaskView } from "../logic/task-overview";

/**
 * Minimalizovaný asistent: malá lišta vpravo dole nad minimapou. Ukazuje aktivní úkol, jeho stav
 * a počet úkolů, aby uživatel koutkem oka viděl, že asistent pracuje nebo doběhl. Klik ji rozbalí.
 */
export default function MinimizedBar({
  barRef,
  task,
  count,
  othersNew,
  onExpand,
  onClose,
}: {
  barRef: Ref<HTMLElement>;
  task: TaskView | null;
  count: number;
  othersNew: boolean;
  onExpand: () => void;
  onClose: () => void;
}) {
  return (
    <aside ref={barRef} className="assistant-panel__mini" aria-label="Asistent (minimalizovaný)">
      <button type="button" className="assistant-panel__mini-open" title="Rozbalit asistenta" onClick={onExpand}>
        <span className={`assistant-panel__status assistant-panel__status--${task?.status ?? "ready"}`}>
          <span className="assistant-panel__status-dot" aria-hidden="true" />
        </span>
        <span className="assistant-panel__mini-text">
          <span className="assistant-panel__mini-title">{task ? task.title : "Asistent"}</span>
          <span className="assistant-panel__mini-meta">
            {task ? task.statusWord : "žádný úkol"} · {tasksCount(count)}
            {othersNew && <span className="assistant-panel__mini-new"> · nové</span>}
          </span>
        </span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true" className="assistant-panel__mini-chevron">
          <path d="m6 15 6-6 6 6" />
        </svg>
      </button>
      <button type="button" className="assistant-panel__mini-close" aria-label="Zavřít asistenta" title="Zavřít asistenta" onClick={onClose}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
          <path d="M6 6l12 12M18 6 6 18" />
        </svg>
      </button>
    </aside>
  );
}
