import { useState } from "react";
import { DATA_KINDS, type DataKind, type EdgeData, type FlowEdge } from "../../logic/flow-types";
import { parseJsonField, pretty } from "../../node-inspector/logic/node-fields";
import { edgeData, KIND_GLYPH, KIND_LABEL } from "../logic/edge-data";
import "../styles/edge-data-panel.css";

type Props = {
  edge: FlowEdge; readOnly: boolean;
  /** Příklad zdrojového uzlu, který hrana zdědí, když nemá vlastní (`inheritedExample`). */
  inherited: { value: unknown; from: string } | null;
  /** Proč cíl druh nepřijímá (`edgeKindError`); null = přijímá. */
  kindError: (kind: DataKind) => string | null;
  /** Uložené `data` (nebo `undefined` = bez dat) jdou nahoru; ukládá rodič. */
  onSave: (data: EdgeData | undefined) => void; onClose: () => void;
};

/** Panel „Co tu letí“: druh dat, schéma a příklad vybrané hrany. Neplatný JSON nebo druh, který cíl nepřijímá, ukáže
 * chybu u pole a nic neodešle. Bez vlastního příkladu ukáže zděděný ze zdrojového uzlu s popiskem „zděděno“. */
export default function EdgeDataPanel({ edge, readOnly, inherited, kindError, onSave, onClose }: Props) {
  const data = edgeData(edge);
  const [kind, setKind] = useState<DataKind | "">(data?.kind ?? "");
  const [schema, setSchema] = useState(pretty(data?.schema)), [example, setExample] = useState(pretty(data?.example));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const save = () => {
    const next: Record<string, string> = {}, parsed = { schema: parseJsonField(schema, true), example: parseJsonField(example, false) };
    if (parsed.schema && "error" in parsed.schema) next.schema = parsed.schema.error;
    if (parsed.example && "error" in parsed.example) next.example = parsed.example.error;
    if (!kind && (schema.trim() || example.trim())) next.kind = "Vyberte druh dat.";
    else if (kind && kindError(kind)) next.kind = kindError(kind)!;
    setErrors(next);
    if (Object.keys(next).length) return;
    const value = (key: "schema" | "example") => { const item = parsed[key]; return "value" in item ? item.value : undefined; };
    onSave(kind ? { kind, ...(value("schema") !== undefined ? { schema: value("schema") } : {}), ...(value("example") !== undefined ? { example: value("example") } : {}) } : undefined);
  };
  const showInherited = !example.trim() && inherited;
  return <aside className="edge-data-panel" aria-label="Co tu letí" data-testid="edge-data-panel">
    <header className="edge-data-panel__head">
      <span className="edge-data-panel__title"><b>Co tu letí</b><small className="edge-data-panel__muted">{edge.source_node} → {edge.target_node}{edge.via ? ` · ${edge.via}` : ""}</small></span>
      <button type="button" className="edge-data-panel__close" aria-label="Zavřít panel" onClick={onClose}>×</button>
    </header>
    <label className="edge-data-panel__field">
      <span className="edge-data-panel__key">Druh dat</span>
      <select className={`edge-data-panel__input${kind ? ` edge-data-panel__input--${kind}` : ""}`} disabled={readOnly} value={kind} data-testid="edge-data-kind"
        onChange={(event) => setKind(event.target.value as DataKind | "")}>
        <option value="">— neurčeno —</option>
        {DATA_KINDS.map((item) => <option key={item} value={item}>{KIND_GLYPH[item]} {KIND_LABEL[item]}</option>)}
      </select>
      {errors.kind && <span className="edge-data-panel__error" role="alert" data-testid="edge-data-error-kind">{errors.kind}</span>}
    </label>
    <label className="edge-data-panel__field">
      <span className="edge-data-panel__key">Schéma<small className="edge-data-panel__muted">JSON objekt</small></span>
      <textarea className="edge-data-panel__input edge-data-panel__input--code" readOnly={readOnly} rows={6} spellCheck={false} value={schema} data-testid="edge-data-schema"
        placeholder='{ "type": "object", "properties": {} }' onChange={(event) => setSchema(event.target.value)}/>
      {errors.schema && <span className="edge-data-panel__error" role="alert" data-testid="edge-data-error-schema">{errors.schema}</span>}
    </label>
    <label className="edge-data-panel__field">
      <span className="edge-data-panel__key">Příklad{showInherited && <small className="edge-data-panel__inherited" data-testid="edge-data-inherited">zděděno z uzlu {inherited.from}</small>}</span>
      <textarea className="edge-data-panel__input edge-data-panel__input--code" readOnly={readOnly} rows={6} spellCheck={false} value={example} data-testid="edge-data-example"
        placeholder='{ "vyska": 180 }' onChange={(event) => setExample(event.target.value)}/>
      {errors.example && <span className="edge-data-panel__error" role="alert" data-testid="edge-data-error-example">{errors.example}</span>}
    </label>
    {showInherited && <pre className="edge-data-panel__preview" data-testid="edge-data-preview">{pretty(inherited.value)}</pre>}
    {!readOnly && <button type="button" className="edge-data-panel__save" data-testid="edge-data-save" onClick={save}>Uložit data hrany</button>}
  </aside>;
}
