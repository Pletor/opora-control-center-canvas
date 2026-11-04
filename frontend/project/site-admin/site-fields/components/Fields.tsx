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
export function TextField({ label, value, placeholder, hint, mono = false, wide = false, maxLength = 200, type = "text", onChange }: {
  label: string; value: string; placeholder?: string; hint?: string; mono?: boolean; wide?: boolean; maxLength?: number;
  type?: "text" | "email" | "url"; onChange: (value: string) => void;
}) {
  return <Field label={label} hint={hint} wide={wide}>
    <input className={"site-fields__input" + (mono ? " site-fields__input--mono" : "")} value={value} placeholder={placeholder} type={type}
      spellCheck={false} maxLength={maxLength} onChange={(event) => onChange(event.target.value)}/>
  </Field>;
}

/** Delší text (popis, právní řádek, JSON-LD). `rows` určuje výšku, `mono` kód. */
export function TextArea({ label, value, placeholder, hint, rows = 3, mono = false, maxLength = 2000, onChange }: {
  label: string; value: string; placeholder?: string; hint?: string; rows?: number; mono?: boolean; maxLength?: number; onChange: (value: string) => void;
}) {
  return <Field label={label} hint={hint} wide>
    <textarea className={"site-fields__input site-fields__textarea" + (mono ? " site-fields__input--mono" : "")} value={value} rows={rows}
      placeholder={placeholder} spellCheck={!mono} maxLength={maxLength} onChange={(event) => onChange(event.target.value)}/>
  </Field>;
}

/** Celé číslo s mezemi; prázdné nebo mimo meze se nehlásí, aby rozepsané číslo neskákalo. */
export function NumberField({ label, value, min, max, hint, onChange }: {
  label: string; value: number; min: number; max: number; hint?: string; onChange: (value: number) => void;
}) {
  return <Field label={label} hint={hint}>
    <input className="site-fields__input" type="number" value={value} min={min} max={max} step={1}
      onChange={(event) => { const next = Number(event.target.value); if (event.target.value && Number.isInteger(next) && next >= min && next <= max) onChange(next); }}/>
  </Field>;
}

/** Zapnuto / vypnuto s popiskem vedle zaškrtávátka; `hint` řekne, co to na webu udělá. */
export function Toggle({ label, checked, hint, disabled = false, onChange }: {
  label: string; checked: boolean; hint?: string; disabled?: boolean; onChange: (checked: boolean) => void;
}) {
  return <label className="site-fields__toggle">
    <input type="checkbox" className="site-fields__check" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)}/>
    <span className="site-fields__toggle-text">{label}{hint && <small className="site-fields__hint">{hint}</small>}</span>
  </label>;
}

/** Výběr z pevných možností; první prázdná možnost říká, co platí bez volby (`empty: null` = volba je povinná). */
export function SelectField({ label, value, options, empty = "Nenastaveno", hint, onChange }: {
  label: string; value: string; options: Option[]; empty?: string | null; hint?: string; onChange: (value: string) => void;
}) {
  return <Field label={label} hint={hint}>
    <select className="site-fields__input" value={value} onChange={(event) => onChange(event.target.value)}>
      {empty !== null && <option value="">{empty}</option>}
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
export function Segments({ label, value, options, required = false, onChange }: {
  label: string; value: string; options: Option[]; required?: boolean; onChange: (value: string) => void;
}) {
  return <div className="site-fields__field" role="group" aria-label={label}>
    <span className="site-fields__label">{label}</span>
    <span className="site-fields__segments">
      {options.map((option) => <button key={option.value} type="button" aria-pressed={value === option.value}
        className={"site-fields__segment" + (value === option.value ? " site-fields__segment--on" : "")}
        onClick={() => onChange(value === option.value && !required ? "" : option.value)}>{option.label}</button>)}
    </span>
  </div>;
}
