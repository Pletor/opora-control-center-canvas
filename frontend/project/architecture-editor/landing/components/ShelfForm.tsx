import { useState } from "react";

/** Malý formulář panelu Komponenty: titulek a jedno doplňkové pole (štítky složky nebo popis plátna). Odeslání hlásí
 *  rodiči; prázdný titulek odeslat nejde. */
export default function ShelfForm({ testId, title, extra, submit, busy, onSubmit, onCancel }: {
  testId: string; title: string; extra: string; submit: string; busy: boolean; onSubmit: (title: string, extra: string) => void; onCancel: () => void;
}) {
  const [name, setName] = useState(""), [more, setMore] = useState("");
  return <form className="component-shelf__form" data-testid={testId} onSubmit={(event) => { event.preventDefault(); if (name.trim()) onSubmit(name, more); }}>
    <input className="component-shelf__input" autoFocus required maxLength={200} placeholder={title} aria-label={title} value={name} onChange={(event) => setName(event.target.value)}/>
    <input className="component-shelf__input" maxLength={2000} placeholder={extra} aria-label={extra} value={more} onChange={(event) => setMore(event.target.value)}/>
    <button type="submit" className="component-shelf__button" disabled={busy || !name.trim()}>{submit}</button>
    <button type="button" className="component-shelf__button" onClick={onCancel}>Zrušit</button>
  </form>;
}
