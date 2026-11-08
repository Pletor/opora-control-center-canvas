import { newResearchTask, taskProblem, type ResearchTask } from "../logic/research-decision";

type Props = { tasks: ResearchTask[]; existing: boolean; nodeNames: Map<string, string>; disabled: boolean; allowNew: boolean;
  onChange: (tasks: ResearchTask[]) => void; onMode: (existing: boolean) => void; onSubmit: () => void };
export default function ResearchDecisionTasks({ tasks, existing, nodeNames, disabled, allowNew, onChange, onMode, onSubmit }: Props) {
  const change = (ref: string, patch: Partial<ResearchTask>) => onChange(tasks.map(task => task.ref === ref ? { ...task, ...patch } : task));
  const problem = taskProblem(tasks, existing);
  return <form className="research-decision__form" onSubmit={event => { event.preventDefault(); if (!problem) onSubmit(); }}>
    <fieldset disabled={disabled}><legend>Konkrétní realizační úkoly</legend>
      <label>Způsob návrhu<select value={existing ? "existing" : "new"} onChange={event => onMode(event.target.value === "existing")}>
        <option value="new" disabled={!allowNew}>Nové úkoly ve Struktuře</option><option value="existing">Doplnit existující úkoly</option>
      </select></label>
      {existing && <p>Aktualizace zadání zachová současné závislosti karet ve Struktuře.</p>}
      {tasks.map((task, index) => <fieldset className="research-decision__task" key={task.ref}><legend>Úkol {index + 1}</legend>
        {existing ? <label>Karta ve Struktuře<select required value={task.nodeId ?? ""} onChange={event => change(task.ref, { nodeId: event.target.value })}>
          <option value="">Vyberte kartu</option>{[...nodeNames].map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select></label> : <label>Zařadit pod kartu<select value={task.parentId ?? ""} onChange={event => change(task.ref, { parentId: event.target.value || undefined })}>
          <option value="">Kořen projektu</option>{[...nodeNames].map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select></label>}
        <label>Název<input required maxLength={500} value={task.title} onChange={event => change(task.ref, { title: event.target.value })} /></label>
        <label>Cíl a rozsah<textarea required maxLength={3500} value={task.goal} onChange={event => change(task.ref, { goal: event.target.value })} /></label>
        <label>Jak ověříme dokončení<textarea required maxLength={3500} value={task.acceptance} onChange={event => change(task.ref, { acceptance: event.target.value })} /></label>
        {!existing && tasks.length > 1 && <div><span>Závisí na dokončení:</span>{tasks.filter(other => other.ref !== task.ref).map(other => <label className="research-decision__check" key={other.ref}>
          <input type="checkbox" checked={task.dependsOn.includes(other.ref)} onChange={event => change(task.ref, { dependsOn: event.target.checked ? [...task.dependsOn, other.ref] : task.dependsOn.filter(ref => ref !== other.ref) })} />
          {other.title || `Úkol ${tasks.indexOf(other) + 1}`}
        </label>)}</div>}
        {tasks.length > 1 && <button type="button" onClick={() => onChange(tasks.filter(item => item.ref !== task.ref).map(item => ({ ...item, dependsOn: item.dependsOn.filter(ref => ref !== task.ref) })))}>Odebrat úkol</button>}
      </fieldset>)}
      <button type="button" disabled={tasks.length >= 50} onClick={() => onChange([...tasks, newResearchTask()])}>Přidat úkol</button>
      {problem && <p>{problem}</p>}
      <button type="submit" disabled={!!problem}>Předložit návrh OporaHubu</button>
    </fieldset>
  </form>;
}
