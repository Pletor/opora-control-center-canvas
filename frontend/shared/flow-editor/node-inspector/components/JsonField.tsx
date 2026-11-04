import { useState } from "react";
import { parseJsonField, pretty } from "../logic/node-fields";

/** JSON editor jednoho pole uzlu: odsazený text, ověření při opuštění pole, chyba zůstane u pole a do grafu nejde. */
export default function JsonField({ label, hint, value, object, readOnly, onCommit }: {
  label: string; hint: string; value: unknown; object: boolean; readOnly: boolean; onCommit: (value: unknown) => void;
}) {
  const [raw, setRaw] = useState(pretty(value)), [error, setError] = useState("");
  const commit = () => {
    if (raw === pretty(value)) return;
    const parsed = parseJsonField(raw, object);
    if ("error" in parsed) setError(parsed.error); else { setError(""); onCommit(parsed.value); }
  };
  return <label className="node-inspector__field node-inspector__field--block">
    <span className="node-inspector__key">{label}<small className="node-inspector__kind">{hint}</small></span>
    <textarea className="node-inspector__input node-inspector__input--json" readOnly={readOnly} rows={6} spellCheck={false} value={raw}
      placeholder={object ? '{ "type": "object", "properties": {} }' : '[{ "json": {} }]'} onChange={(event) => setRaw(event.target.value)} onBlur={commit}/>
    {error && <span className="node-inspector__error" role="alert">{error}</span>}
  </label>;
}
