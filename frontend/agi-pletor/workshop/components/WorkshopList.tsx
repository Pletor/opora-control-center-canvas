import { useId, useState, type FormEvent } from "react";
import { NAME_RE } from "../logic/workshop-state";

type Item = { name: string; hint: string };
type Props = {
  title: string; newLabel: string; items: Item[]; selected: string | null; busy: boolean;
  onSelect: (name: string) => void; onCreate: (name: string) => void;
};

/** Sloupec seznamu v Dílně (Skilly nebo Funkce): položky jako tlačítka a pod nimi založení nové položky jménem. */
export default function WorkshopList({ title, newLabel, items, selected, busy, onSelect, onCreate }: Props) {
  const [name, setName] = useState("");
  const inputId = useId();
  const valid = NAME_RE.test(name);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid) return;
    onCreate(name);
    setName("");
  };
  return (
    <section className="pletor-workshop__list" aria-label={title}>
      <h3 className="pletor-workshop__list-title">{title}</h3>
      {items.length === 0 && <p className="pletor-workshop__empty">Zatím nic.</p>}
      <ul className="pletor-workshop__items">
        {items.map((item) => (
          <li key={item.name}>
            <button type="button" className="pletor-workshop__item" aria-pressed={item.name === selected} title={item.hint || undefined}
              onClick={() => onSelect(item.name)}>
              {item.name}
            </button>
          </li>
        ))}
      </ul>
      <form className="pletor-workshop__new" onSubmit={submit}>
        <label className="pletor-workshop__new-label" htmlFor={inputId}>{newLabel}</label>
        <input id={inputId} className="pletor-workshop__new-input" value={name} placeholder="nazev-s-pomlckami" spellCheck={false}
          aria-invalid={name !== "" && !valid} onChange={(event) => setName(event.target.value)} />
        <button type="submit" className="pletor-workshop__button" disabled={!valid || busy}>Založit</button>
      </form>
    </section>
  );
}
