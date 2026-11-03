import { useState } from "react";
import { fieldRows, parseField, parseNewParam, type FieldRow } from "../logic/inspector-fields";

type Props = { params: Record<string, unknown> | undefined; readOnly: boolean; onParam: (key: string, value: unknown) => void };

/** Parametry uzlu jako pole podle druhu hodnoty. Zápis se ověří při opuštění pole (číslo, JSON); chyba zůstane u pole
 * a do grafu nejde. Na konci řádek pro nový parametr. V režimu běhu jen ke čtení. */
export default function ParamFields({ params, readOnly, onParam }: Props) {
  const rows = fieldRows(params);
  return <div className="node-inspector__fields">
    {!rows.length && <p className="node-inspector__muted">Uzel nemá parametry.</p>}
    {rows.map((row) => <ParamField key={row.key + row.raw} row={row} readOnly={readOnly} onParam={onParam}/>)}
    {!readOnly && <NewParam params={params} onParam={onParam}/>}
  </div>;
}

function ParamField({ row, readOnly, onParam }: { row: FieldRow; readOnly: boolean; onParam: Props["onParam"] }) {
  const [raw, setRaw] = useState(row.raw), [error, setError] = useState("");
  const commit = (text: string) => {
    if (text === row.raw) return;
    const parsed = parseField(row.kind, text);
    if ("error" in parsed) setError(parsed.error); else { setError(""); onParam(row.key, parsed.value); }
  };
  return <label className="node-inspector__field">
    <span className="node-inspector__key">{row.key}<small className="node-inspector__kind">{row.kind}</small></span>
    {row.kind === "boolean"
      ? <input type="checkbox" disabled={readOnly} checked={raw === "true"} onChange={(event) => { const text = String(event.target.checked); setRaw(text); commit(text); }}/>
      : row.kind === "json"
        ? <textarea className="node-inspector__input node-inspector__input--json" readOnly={readOnly} value={raw} rows={2}
          onChange={(event) => setRaw(event.target.value)} onBlur={() => commit(raw)}/>
        : <input className="node-inspector__input" readOnly={readOnly} inputMode={row.kind === "number" ? "decimal" : undefined} value={raw}
          onChange={(event) => setRaw(event.target.value)} onBlur={() => commit(raw)} onKeyDown={(event) => { if (event.key === "Enter") commit(raw); }}/>}
    {!readOnly && <button type="button" className="node-inspector__drop" aria-label={`Odebrat parametr ${row.key}`} onClick={() => onParam(row.key, undefined)}>×</button>}
    {error && <span className="node-inspector__error" role="alert">{error}</span>}
  </label>;
}

function NewParam({ params, onParam }: { params: Props["params"]; onParam: Props["onParam"] }) {
  const [key, setKey] = useState(""), [raw, setRaw] = useState(""), [error, setError] = useState("");
  const add = () => {
    const parsed = parseNewParam(key, raw, params);
    if ("error" in parsed) { setError(parsed.error); return; }
    onParam(parsed.key, parsed.value); setKey(""); setRaw(""); setError("");
  };
  return <div className="node-inspector__new">
    <input className="node-inspector__input" placeholder="klíč" aria-label="Klíč nového parametru" value={key} onChange={(event) => setKey(event.target.value)}/>
    <input className="node-inspector__input" placeholder="hodnota (JSON nebo text)" aria-label="Hodnota nového parametru" value={raw} onChange={(event) => setRaw(event.target.value)}/>
    <button type="button" className="node-inspector__button" onClick={add}>Přidat</button>
    {error && <span className="node-inspector__error" role="alert">{error}</span>}
  </div>;
}
