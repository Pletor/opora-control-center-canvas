import { useId } from "react";
import type { Measure } from "../logic/workshop-api";
import type { ToolDoc } from "../logic/workshop-state";
import WorkshopMeasure from "./WorkshopMeasure";
import WorkshopPending from "./WorkshopPending";

type Props = {
  doc: ToolDoc | null; measure: Measure | null; dirty: boolean; pending: boolean; busy: boolean;
  onEdit: (patch: { code?: string; cases?: string }) => void; onSave: () => void; onMeasure: () => void; onDiscard: () => void; onKeep: () => void;
};

/** Okno editoru funkce: kód `<nazev>.py`, pod ním případy měření (JSON), Uložit, Změřit a výsledek měření. */
export default function WorkshopToolEditor({ doc, measure, dirty, pending, busy, onEdit, onSave, onMeasure, onDiscard, onKeep }: Props) {
  const codeId = useId(), casesId = useId();
  if (!doc) return <section className="pletor-workshop__editor" aria-label="Funkce"><p className="pletor-workshop__empty">Vyber funkci vlevo.</p></section>;
  return (
    <section className="pletor-workshop__editor" aria-label="Funkce">
      <header className="pletor-workshop__editor-head">
        <h3 className="pletor-workshop__editor-title">Funkce · {doc.name}{dirty && <span className="pletor-workshop__dirty"> ● neuloženo</span>}</h3>
        <button type="button" className="pletor-workshop__button pletor-workshop__button--primary" disabled={!dirty || busy} onClick={onSave}>Uložit</button>
        {/* Měří se uložený soubor na serveru, proto s neuloženou změnou nejde. */}
        <button type="button" className="pletor-workshop__button" disabled={dirty || busy} title={dirty ? "Nejdřív ulož, měří se uložená funkce" : undefined}
          onClick={onMeasure}>Změřit</button>
      </header>
      {pending && <WorkshopPending onDiscard={onDiscard} onKeep={onKeep} />}
      <label className="pletor-workshop__field-label" htmlFor={codeId}>{doc.name}.py</label>
      <textarea id={codeId} className="pletor-workshop__code" value={doc.code} spellCheck={false} onChange={(event) => onEdit({ code: event.target.value })} />
      <label className="pletor-workshop__field-label" htmlFor={casesId}>{doc.name}.cases.json</label>
      <textarea id={casesId} className="pletor-workshop__code pletor-workshop__code--cases" value={doc.cases} spellCheck={false}
        onChange={(event) => onEdit({ cases: event.target.value })} />
      {measure && measure.name === doc.name && <WorkshopMeasure measure={measure} />}
    </section>
  );
}
