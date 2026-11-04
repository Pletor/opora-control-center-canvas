import { useState } from "react";
import type { FlowCase, FlowNode } from "../../logic/flow-types";
import type { CaseMark } from "../logic/flow-cases";
import CaseEditor from "./CaseEditor";
import "../styles/flow-cases.css";

type Props = {
  cases: readonly FlowCase[]; nodes: readonly FlowNode[]; selectedId: string | null; marks: Readonly<Record<string, CaseMark>>; disabled: boolean;
  onSelect: (id: string | null) => void; onAdd: () => void; onRemove: (id: string) => void; onChange: (flowCase: FlowCase) => void;
};
const MARK_TEXT: Record<CaseMark, string> = { ok: "shoda s očekáváním", fail: "neshoda s očekáváním", idle: "nespuštěno nebo bez očekávání" };

/** Lišta případů nad plátnem: výběr případu se značkou výsledku, „+ Případ“, smazání a editor vybraného případu (jméno,
 * popis, start, vstup, prostředí, očekávání). Neukládá: každou platnou úpravu hlásí rodiči, který případy drží v grafu. */
export default function FlowCasesBar({ cases, nodes, selectedId, marks, disabled, onSelect, onAdd, onRemove, onChange }: Props) {
  const [editing, setEditing] = useState(false);
  const selected = cases.find((item) => item.id === selectedId) ?? null;
  return <div className="flow-cases" data-testid="flow-cases">
    <div className="flow-cases__bar">
      <span className="flow-cases__label">Případ</span>
      <span className={`flow-cases__mark flow-cases__mark--${selected ? marks[selected.id] ?? "idle" : "idle"}`} role="img" aria-label={MARK_TEXT[selected ? marks[selected.id] ?? "idle" : "idle"]}
        title={MARK_TEXT[selected ? marks[selected.id] ?? "idle" : "idle"]} data-testid="flow-case-mark"/>
      <select className="flow-cases__select" aria-label="Vybraný případ" disabled={disabled || !cases.length} value={selected?.id ?? ""} data-testid="flow-case-select"
        onChange={(event) => onSelect(event.target.value || null)}>
        {!cases.length && <option value="">žádný případ</option>}
        {cases.map((item) => <option key={item.id} value={item.id}>{{ ok: "● ", fail: "● ", idle: "○ " }[marks[item.id] ?? "idle"]}{item.name}</option>)}
      </select>
      <button type="button" className="flow-cases__button" disabled={disabled} data-testid="flow-case-add" onClick={() => { onAdd(); setEditing(true); }}>+ Případ</button>
      {selected && <>
        <button type="button" className="flow-cases__button" disabled={disabled} aria-pressed={editing} data-testid="flow-case-edit" onClick={() => setEditing(!editing)}>{editing ? "Zavřít editor" : "Upravit"}</button>
        <button type="button" className="flow-cases__button" disabled={disabled} data-testid="flow-case-remove"
          onClick={() => { if (window.confirm(`Smazat případ „${selected.name}“?`)) { onRemove(selected.id); setEditing(false); } }}>Smazat</button>
        {selected.description && <span className="flow-cases__description">{selected.description}</span>}
      </>}
    </div>
    {editing && selected && !disabled && <CaseEditor key={selected.id} flowCase={selected} nodes={nodes} onSave={onChange}/>}
  </div>;
}
