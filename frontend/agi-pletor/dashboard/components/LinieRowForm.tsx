import { useState, type FormEvent } from "react";

type Props = { onSubmit: (body: object) => Promise<boolean>; onClose: () => void };

const TYPES = [["items", "univerzální díl"], ["work", "práce"], ["experiment", "experiment"], ["fix", "oprava"]] as const;

/** Nový řádek editoru: název, typ, výchozí bod a cíl. Řádek je jen popisek, větev nezakládá; zápis hlásí rodiči. */
export default function LinieRowForm({ onSubmit, onClose }: Props) {
  const [name, setName] = useState("");
  const [type, setType] = useState("work");
  const [base, setBase] = useState("develop");
  const [target, setTarget] = useState("develop");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    void onSubmit({ name: name.trim(), type, ...(base.trim() ? { base: { branch: base.trim() } } : {}), target: target.trim() || null })
      .then((ok) => { if (ok) { setName(""); onClose(); } });
  };

  return (
    <form className="pletor-dashboard__linie-form" onSubmit={submit} aria-label="Nový řádek">
      <label className="pletor-dashboard__linie-field">název
        <input className="pletor-dashboard__input" value={name} required maxLength={120} placeholder="např. Datový uzel" onChange={(event) => setName(event.target.value)} />
      </label>
      <label className="pletor-dashboard__linie-field">typ
        <select className="pletor-dashboard__input" value={type} onChange={(event) => setType(event.target.value)}>
          {TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      <label className="pletor-dashboard__linie-field">výchozí větev
        <input className="pletor-dashboard__input" value={base} onChange={(event) => setBase(event.target.value)} />
      </label>
      <label className="pletor-dashboard__linie-field">cíl začlenění
        <input className="pletor-dashboard__input" value={target} placeholder="prázdné = zatím neurčeno" onChange={(event) => setTarget(event.target.value)} />
      </label>
      <button type="submit" className="pletor-dashboard__button">Přidat</button>
      <button type="button" className="pletor-dashboard__button" onClick={onClose}>Zrušit</button>
    </form>
  );
}
