// Formulář vybraného momentu. Nahoře zvýrazněné přání člověka („Co tu chci jinak“) a jeho šipky a poznámky,
// pod tím popis momentu a pole stavu podle animace. Všechny změny jdou nahoru přes onChange / onStateChange.
import { annotationSentence, EASE_LABELS, EASE_NAMES, type Annotation, type Moment, type StateValue } from "../logic/storyboard-model";
import type { Field } from "../logic/animations";

export default function MomentForm({ moment, fields, readOnly, selectedAnnotation, canRemove, onChange, onState, onAnnotationText, onAnnotationSelect, onAnnotationRemove, onDuplicate, onRemove }: {
  moment: Moment;
  fields: Field[];
  readOnly: boolean;
  selectedAnnotation: number;
  canRemove: boolean;
  onChange: (patch: Partial<Moment>) => void;
  onState: (key: string, value: StateValue) => void;
  onAnnotationText: (index: number, text: string) => void;
  onAnnotationSelect: (index: number) => void;
  onAnnotationRemove: (index: number) => void;
  onDuplicate: () => void;
  onRemove: () => void;
}) {
  const text = (label: string, key: "title" | "shows" | "changes") => (
    <label className="storyboard__field">{label}
      <input type="text" value={moment[key]} maxLength={500} disabled={readOnly} onChange={(e) => onChange({ [key]: e.target.value })} />
    </label>
  );
  function stateInput(f: Field) {
    const v = moment.state[f.key];
    if (f.kind === "boolean") return <input type="checkbox" checked={v === true} disabled={readOnly} onChange={(e) => onState(f.key, e.target.checked)} />;
    if (f.kind === "color") return <input type="color" value={typeof v === "string" ? v : "#ffffff"} disabled={readOnly} onChange={(e) => onState(f.key, e.target.value)} />;
    if (f.kind === "string") return <input type="text" value={typeof v === "string" ? v : ""} maxLength={100} disabled={readOnly} onChange={(e) => onState(f.key, e.target.value)} />;
    return <input type="number" min={f.min} max={f.max} step={f.step ?? 0.01} value={typeof v === "number" ? v : 0} disabled={readOnly}
      onChange={(e) => { if (e.target.value !== "" && Number.isFinite(Number(e.target.value))) onState(f.key, Number(e.target.value)); }} />;
  }
  return (
    <form className="storyboard__form" onSubmit={(e) => e.preventDefault()}>
      <div className={"storyboard__comment" + (moment.comment ? "" : " storyboard__comment--empty")}>
        <label htmlFor="moment-comment">Co tu chci jinak</label>
        <textarea id="moment-comment" value={moment.comment} maxLength={2000} rows={3} disabled={readOnly} placeholder="bez přání" onChange={(e) => onChange({ comment: e.target.value, answered: false })} />
        {(moment.comment.trim() !== "" || moment.annotations.length > 0 || moment.sketch) && (
          <label className="storyboard__answered">
            <input type="checkbox" checked={moment.answered === true} disabled={readOnly} onChange={(e) => onChange({ answered: e.target.checked })} />
            Odpovězeno
          </label>
        )}
      </div>
      <ul className="storyboard__annotations" aria-label="Šipky a poznámky momentu">
        {moment.annotations.map((a: Annotation, i) => (
          <li key={i} className={i === selectedAnnotation ? "storyboard__annotation storyboard__annotation--selected" : "storyboard__annotation"}>
            <button type="button" className="storyboard__annotation-pick" onClick={() => onAnnotationSelect(i)}>{annotationSentence({ ...a, text: "" }).replace(/: $/, "")}</button>
            <input type="text" value={a.text} maxLength={200} disabled={readOnly} placeholder="text" aria-label={`Text anotace ${i + 1}`} onChange={(e) => onAnnotationText(i, e.target.value)} />
            <button type="button" disabled={readOnly} onClick={() => onAnnotationRemove(i)} aria-label={`Smazat anotaci ${i + 1}`}>Smazat</button>
          </li>
        ))}
        {moment.annotations.length === 0 && <li className="storyboard__annotations-empty">Bez šipek a poznámek. Nástroj Šipka nebo Poznámka je přidá na snímek.</li>}
      </ul>
      <label className="storyboard__field">Čas (s)
        <input type="number" min={0} step={0.1} value={moment.t} disabled={readOnly} onChange={(e) => { if (e.target.value !== "") onChange({ t: Number(e.target.value) }); }} />
      </label>
      {text("Název", "title")}
      {text("Co divák vidí", "shows")}
      {text("Co se mění do dalšího", "changes")}
      <label className="storyboard__field">Průběh k dalšímu momentu
        <select value={moment.ease} disabled={readOnly} onChange={(e) => onChange({ ease: e.target.value as Moment["ease"] })}>
          {EASE_NAMES.map((n) => <option key={n} value={n}>{EASE_LABELS[n]}</option>)}
        </select>
      </label>
      {fields.map((f) => <label key={f.key} className="storyboard__field">{f.label}{stateInput(f)}</label>)}
      <div className="storyboard__form-actions">
        <button type="button" disabled={readOnly} onClick={onDuplicate}>Duplikovat</button>
        <button type="button" disabled={readOnly || !canRemove} onClick={onRemove}>Smazat moment</button>
      </div>
    </form>
  );
}
