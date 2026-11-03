import { useState } from "react";
import { MAX_FAMILIES } from "../logic/typography";

/** Rodiny písma: klíč (`--font-<klíč>`) a stack. Klíč se potvrdí až opuštěním pole, stack se píše rovnou. */
function FamilyRow({ name, stack, taken, onChange, onRemove }: { name: string; stack: string; taken: string[]; onChange: (key: string, stack: string) => void; onRemove: () => void }) {
  const [key, setKey] = useState(name);
  const bad = key !== name && (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(key) || taken.includes(key));
  const commit = () => { if (key !== name && !bad) onChange(key, stack); else setKey(name); };
  return <div className="ds-type__family">
    <input className={"ds-type__input ds-type__input--mono" + (bad ? " ds-type__input--problem" : "")} aria-label="Klíč rodiny" value={key} maxLength={64}
      onChange={(event) => setKey(event.target.value)} onBlur={commit} onKeyDown={(event) => { if (event.key === "Enter") commit(); }}/>
    <input className="ds-type__input ds-type__input--wide" aria-label={"Stack rodiny " + name} value={stack} maxLength={200} spellCheck={false}
      placeholder="Inter, system-ui, sans-serif" onChange={(event) => onChange(name, event.target.value)}/>
    <code className="ds-type__var">var(--font-{name})</code>
    <button type="button" className="ds-type__remove" aria-label={"Odebrat rodinu " + name} onClick={onRemove}>×</button>
  </div>;
}

export default function FamiliesEditor({ families, onChange, onAdd, onRemove }: {
  families: Record<string, string>; onChange: (key: string, next: string, stack: string) => void; onAdd: (key: string) => void; onRemove: (key: string) => void;
}) {
  const keys = Object.keys(families);
  const fresh = ["sans", "serif", "mono", "display"].find((key) => !keys.includes(key)) ?? `family-${keys.length + 1}`;
  return <div className="ds-type__block">
    <h4 className="ds-type__title">Rodiny písma</h4>
    {!keys.length && <p className="ds-type__empty">Zatím žádná rodina. Rodina je stack písma, na který se styly odkazují.</p>}
    {keys.map((key) => <FamilyRow key={key} name={key} stack={families[key]} taken={keys} onChange={(next, stack) => onChange(key, next, stack)} onRemove={() => onRemove(key)}/>)}
    <button type="button" className="ds-type__add" disabled={keys.length >= MAX_FAMILIES} onClick={() => onAdd(fresh)}>+ Rodina</button>
  </div>;
}
