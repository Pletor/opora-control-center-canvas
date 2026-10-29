import type { QueueTask } from "../logic/heart-api";
import { groupQueue, holderLabel } from "../logic/queue";

/** Řádek úkolu: název, stav a držitel; rozbalí se na `do` a `doneWhen`. Jen ke čtení. */
function QueueRow({ task, label }: { task: QueueTask; label: string }) {
  const doneWhen = task.body.doneWhen ?? [];
  return (
    <li className="heart-channel__task">
      <details className="heart-channel__task-details">
        <summary className="heart-channel__task-summary">
          <span className="heart-channel__task-title">{task.title}</span>
          <span className={`heart-channel__task-status heart-channel__task-status--${task.status}`}>{label}</span>
          <span className="heart-channel__task-holder">{holderLabel(task)}</span>
        </summary>
        <p className="heart-channel__task-do">{task.body.do}</p>
        {doneWhen.length > 0 && (
          <ul className="heart-channel__task-done-when" aria-label="Hotovo, když">
            {doneWhen.map((item, index) => <li key={index}>{item}</li>)}
          </ul>
        )}
      </details>
    </li>
  );
}

/** Fronta úkolů pracovního prostoru po skupinách ready / assigned / done / failed / cancelled. */
export default function Queue({ tasks, loaded }: { tasks: QueueTask[]; loaded: boolean }) {
  const groups = groupQueue(tasks);
  return (
    <section className="heart-channel__section" aria-label="Fronta">
      <h3 className="heart-channel__heading">Fronta</h3>
      {groups.length === 0 && <p className="heart-channel__empty">{loaded ? "Fronta je prázdná." : "Načítám frontu…"}</p>}
      {groups.map((group) => (
        <div key={group.status} className="heart-channel__group">
          <h4 className="heart-channel__group-label">
            {group.label} <span className="heart-channel__count">{group.tasks.length}</span>
          </h4>
          <ul className="heart-channel__tasks">
            {group.tasks.map((task) => <QueueRow key={task.taskId} task={task} label={group.label} />)}
          </ul>
        </div>
      ))}
    </section>
  );
}
