import { useState } from "react";
import { PRESET_VARIANTS, slugProblem, type Buttons } from "../logic/button-model";

/** Varianty tlačítek jako řada štítků (vybraná svítí), odebrání a přidání podle jména. Prázdný systém nabídne
 *  předvolby primary, secondary, outline, ghost a link jedním kliknutím. */
export default function VariantList({ buttons, selected, onSelect, onAdd, onAddAll, onRemove }: {
  buttons: Buttons; selected: string; onSelect: (slug: string) => void; onAdd: (slug: string) => void; onAddAll: () => void; onRemove: (slug: string) => void;
}) {
  const [name, setName] = useState("");
  const slugs = Object.keys(buttons.variants);
  const missing = Object.keys(PRESET_VARIANTS).filter((slug) => !buttons.variants[slug]);
  const problem = name ? slugProblem(name, buttons) : "";
  const add = (slug: string) => { onAdd(slug); setName(""); };
  return <div className="site-buttons__variants" data-testid="button-variants">
    {!slugs.length && <div className="site-buttons__empty">
      <p className="site-buttons__hint">Web zatím nemá žádná tlačítka. Začni z předvoleb a uprav je, nebo přidej vlastní variantu.</p>
      <button type="button" className="site-buttons__primary-action" onClick={onAddAll}>Začít z předvoleb (primary, secondary, outline, ghost, link)</button>
    </div>}
    {!!slugs.length && <div className="site-buttons__chips" role="tablist" aria-label="Varianty tlačítek">
      {slugs.map((slug) => <span key={slug} className={"site-buttons__chip" + (slug === selected ? " site-buttons__chip--on" : "")}>
        <button type="button" role="tab" aria-selected={slug === selected} className="site-buttons__chip-name" onClick={() => onSelect(slug)}>
          {buttons.variants[slug].label || slug}<code className="site-buttons__chip-class">ds-btn--{slug}</code>
        </button>
        <button type="button" className="site-buttons__icon" aria-label={`Odebrat variantu ${slug}`}
          onClick={() => { if (window.confirm(`Odebrat variantu ${slug} i s jejím vlastním CSS?`)) onRemove(slug); }}>×</button>
      </span>)}
    </div>}
    <form className="site-buttons__new" onSubmit={(event) => { event.preventDefault(); if (name && !problem) add(name); }}>
      {missing.map((slug) => <button key={slug} type="button" className="site-buttons__add" onClick={() => add(slug)}>+ {slug}</button>)}
      <input className="site-fields__input site-buttons__new-name" value={name} placeholder="vlastní-varianta" aria-label="Jméno nové varianty" maxLength={32}
        onChange={(event) => setName(event.target.value.toLowerCase())}/>
      <button type="submit" className="site-buttons__add" disabled={!name || !!problem}>+ Přidat</button>
      {problem && <small className="site-buttons__problem" role="alert">{problem}</small>}
    </form>
  </div>;
}
