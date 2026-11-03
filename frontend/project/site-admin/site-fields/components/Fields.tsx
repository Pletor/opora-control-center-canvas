import type { ReactNode } from "react";
import { pickerHex } from "../logic/field-values";
import "../styles/site-fields.css";

type Option = { value: string; label: string };

/** Pole s popiskem nad sebou, jak ho kreslí `image.png` („Styl tlačítka“, „Pozadí tlačítka“). */
export function Field({ label, hint, wide = false, children }: { label: string; hint?: string; wide?: boolean; children: ReactNode }) {
  return <label className={"site-fields__field" + (wide ? " site-fields__field--wide" : "")}>
    <span className="site-fields__label">{label}</span>
    {children}
    {hint && <small className="site-fields__hint">{hint}</small>}
  </label>;
}

/** Text nebo délka. Prázdné pole = nenastaveno; `placeholder` ukazuje, co platí místo něj (zděděná hodnota). */
export function TextField({ label, value, placeholder, hint, mono = false, onChange }: {
  label: string; value: string; placeholder?: string; hint?: string; mono?: boolean; onChange: (value: string) => void;
}) {
  return <Field label={label} hint={hint}>
    <input className={"site-fields__input" + (mono ? " site-fields__input--mono" : "")} value={value} placeholder={placeholder}
      spellCheck={false} maxLength={200} onChange={(event) => onChange(event.target.value)}/>
  </Field>;
}

/** Výběr z pevných možností; první prázdná možnost říká, co platí bez volby. */
export function SelectField({ label, value, options, empty = "Nenastaveno", hint, onChange }: {
  label: string; value: string; options: Option[]; empty?: string; hint?: string; onChange: (value: string) => void;
}) {
  return <Field label={label} hint={hint}>
    <select className="site-fields__input" value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">{empty}</option>
      {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
  </Field>;
}

/** Barva: vzorek s výběrem, text (hex, funkce, `transparent`) a nabídka aliasů `{token}` z Colors. */
export function ColorField({ label, value, placeholder, aliases, onChange, children }: {
  label: string; value: string; placeholder?: string; aliases: string[]; onChange: (value: string) => void; children?: ReactNode;
}) {
  const hex = pickerHex(value || placeholder || "");
  const list = "site-fields-aliases-" + label.replace(/\W+/g, "-");
  return <Field label={label}>
    <span className="site-fields__color">
      <input type="color" className="site-fields__picker" aria-label={label + " – výběr"} value={hex ?? "#888888"}
        onChange={(event) => onChange(event.target.value)}/>
      <input className="site-fields__input site-fields__input--mono site-fields__input--bare" value={value} placeholder={placeholder}
        list={list} spellCheck={false} maxLength={120} aria-label={label} onChange={(event) => onChange(event.target.value)}/>
      <datalist id={list}>{aliases.map((name) => <option key={name} value={`{${name}}`}/>)}</datalist>
    </span>
    {children}
  </Field>;
}

/** Řada voleb jako segmenty (zaoblení rohů, šířka); vybraný segment svítí akcentem. */
export function Segments({ label, value, options, onChange }: { label: string; value: string; options: Option[]; onChange: (value: string) => void }) {
  return <div className="site-fields__field" role="group" aria-label={label}>
    <span className="site-fields__label">{label}</span>
    <span className="site-fields__segments">
      {options.map((option) => <button key={option.value} type="button" aria-pressed={value === option.value}
        className={"site-fields__segment" + (value === option.value ? " site-fields__segment--on" : "")}
        onClick={() => onChange(value === option.value ? "" : option.value)}>{option.label}</button>)}
    </span>
  </div>;
}
