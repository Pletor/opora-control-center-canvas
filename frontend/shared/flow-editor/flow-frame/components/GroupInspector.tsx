import { useState } from "react";
import type { FlowGroup } from "../../logic/flow-types";
import "../styles/flow-frame.css";

type Props = {
  group: FlowGroup; errors: string[]; collapsed: boolean; readOnly: boolean;
  onChange: (patch: Partial<Pick<FlowGroup, "name" | "description">>) => void; onToggle: () => void; onUngroup: () => void; onClose: () => void;
};

/** Inspektor rámce v pravém sloupci: jméno (nesmí být prázdné), popis do 145 znaků, uzly rámce, chyby kontroly grafu
 * u skupiny, sbalit nebo rozbalit a rozpustit rámec (uzly zůstanou). Zápis jde při opuštění pole. */
export default function GroupInspector({ group, errors, collapsed, readOnly, onChange, onToggle, onUngroup, onClose }: Props) {
  const [name, setName] = useState(group.name), [description, setDescription] = useState(group.description ?? "");
  return <aside className="flow-frame__inspector" aria-label={`Rámec ${group.name}`} data-testid="group-inspector">
    <header className="flow-frame__inspector-head">
      <b>Rámec</b>
      <button type="button" className="flow-frame__close" aria-label="Zavřít inspektor rámce" onClick={onClose}>×</button>
    </header>
    <label className="flow-frame__field">Jméno
      <input className="flow-frame__input" readOnly={readOnly} value={name} onChange={(event) => setName(event.target.value)}
        onBlur={() => { if (name.trim() && name !== group.name) onChange({ name: name.trim() }); else setName(group.name); }}/>
    </label>
    <label className="flow-frame__field">Popis <small className="flow-frame__muted">{description.length}/145</small>
      <textarea className="flow-frame__input" readOnly={readOnly} maxLength={145} rows={3} value={description} onChange={(event) => setDescription(event.target.value)}
        onBlur={() => { if (description !== (group.description ?? "")) onChange({ description }); }}/>
    </label>
    <p className="flow-frame__muted">Uzly: {group.nodeIds.join(", ")}</p>
    {errors.length > 0 && <ul className="flow-frame__errors" data-testid="group-inspector-errors">{errors.map((error) => <li key={error}>{error}</li>)}</ul>}
    <div className="flow-frame__actions">
      <button type="button" className="flow-frame__button" onClick={onToggle}>{collapsed ? "Rozbalit" : "Sbalit do jednoho uzlu"}</button>
      {!readOnly && <button type="button" className="flow-frame__button" onClick={onUngroup}>Rozpustit rámec</button>}
    </div>
  </aside>;
}
