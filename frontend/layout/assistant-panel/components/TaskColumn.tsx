import { useMemo, useState } from "react";
import type { AssistantModel } from "../logic/assistant-api";
import { filterTasks, groupTasks, type TaskView } from "../logic/task-overview";
import NewTask from "./NewTask";
import TaskItem from "./TaskItem";

/**
 * Úkoly na celé ploše: trvalý sloupec vlevo. Nahoře „Úkoly N“ a „+ Nový úkol“ s modelem, pod tím
 * hledání v názvech a pak skupiny Pracuje / Čeká na vás / Ostatní, aby bylo hned vidět, kde se něco
 * děje a kde se čeká na odpověď. Hledaný text je jen pohled sloupce; volby hlásí dílek nahoru.
 */
export default function TaskColumn({
  tasks,
  model,
  onModel,
  onCreate,
  onSelect,
  onRename,
  onClose,
}: {
  tasks: TaskView[];
  model: AssistantModel;
  onModel: (model: AssistantModel) => void;
  onCreate: () => void;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => Promise<boolean>;
  onClose: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const groups = useMemo(() => groupTasks(filterTasks(tasks, query)), [tasks, query]);
  return (
    <nav className="assistant-panel__tasks assistant-panel__tasks--column" aria-label="Úkoly asistenta">
      <div className="assistant-panel__tasks-head">
        <span className="assistant-panel__tasks-title" title="Alt+↑ / Alt+↓ přepíná úkoly">
          Úkoly <span className="assistant-panel__tasks-total">{tasks.length}</span>
        </span>
        <NewTask model={model} onModel={onModel} onCreate={onCreate} />
      </div>
      {tasks.length > 0 && (
        <input
          type="search"
          className="assistant-panel__tasks-search"
          aria-label="Hledat v úkolech"
          placeholder="Hledat v úkolech…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Escape" && query) { e.preventDefault(); setQuery(""); /* Esc nejdřív vymaže hledání, panel nezmenší. */ } }}
        />
      )}
      <div className="assistant-panel__task-groups">
        {groups.map((group) => (
          <section key={group.key} className="assistant-panel__task-group" aria-label={group.label}>
            <h3 className="assistant-panel__task-group-label">
              {group.label} <span className="assistant-panel__task-group-count">{group.tasks.length}</span>
            </h3>
            <ul className="assistant-panel__task-list">
              {group.tasks.map((t) => <TaskItem key={t.id} task={t} onSelect={onSelect} onRename={onRename} onClose={onClose} />)}
            </ul>
          </section>
        ))}
        {query && groups.length === 0 && <p className="assistant-panel__hint assistant-panel__tasks-none">Žádný úkol neodpovídá „{query.trim()}“.</p>}
      </div>
    </nav>
  );
}
