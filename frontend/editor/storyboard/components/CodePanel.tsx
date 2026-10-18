// Editor kódu animace (záložka „Kód animace“ vedle formuláře momentu): zdroj modulu, název a pole a vrstvy jako JSON.
// „Použít“ zkontroluje tvar a pošle hotový `CodeSpec` rodiči; ten ho vloží do konceptu a Worker modul znovu načte.
// Dílek nic neukládá, ukládá se stávajícím „Uložit“ storyboardu.
import { useEffect, useState } from "react";
import { SLOW_PAINT_MS, parseCodeDraft } from "../logic/code-module";
import type { CodeSpec } from "../logic/storyboard-model";

const toDraft = (code: CodeSpec) => ({ source: code.source, title: code.title, fields: JSON.stringify(code.fields, null, 2), layers: JSON.stringify(code.layers, null, 2) });

export default function CodePanel({ code, readOnly, workerError, slowMs, onApply }: {
  code: CodeSpec;
  readOnly: boolean;
  /** Chyba modulu nebo kreslení z Workeru; ukáže se pod editorem. */
  workerError: string;
  slowMs: number | null;
  onApply: (code: CodeSpec) => void;
}) {
  const [draft, setDraft] = useState(() => toDraft(code));
  const [localError, setLocalError] = useState("");
  useEffect(() => { setDraft(toDraft(code)); setLocalError(""); }, [code]);
  const edit = (key: keyof typeof draft, value: string) => { setDraft({ ...draft, [key]: value }); setLocalError(""); };
  const apply = () => {
    const parsed = parseCodeDraft(draft);
    if ("error" in parsed) setLocalError(parsed.error); else onApply(parsed.code);
  };
  const error = localError || workerError;
  return (
    <div className="code-panel">
      <label className="code-panel__field">Název animace
        <input type="text" value={draft.title} maxLength={200} disabled={readOnly} onChange={(e) => edit("title", e.target.value)} />
      </label>
      <label className="code-panel__field">Kód animace (ES modul bez importů: fields, layers, paint)
        <textarea className="code-panel__source" value={draft.source} rows={24} spellCheck={false} disabled={readOnly} onChange={(e) => edit("source", e.target.value)} />
      </label>
      <label className="code-panel__field">Pole stavu (fields, JSON)
        <textarea className="code-panel__json" value={draft.fields} rows={6} spellCheck={false} disabled={readOnly} onChange={(e) => edit("fields", e.target.value)} />
      </label>
      <label className="code-panel__field">Vrstvy (layers, JSON)
        <textarea className="code-panel__json" value={draft.layers} rows={4} spellCheck={false} disabled={readOnly} onChange={(e) => edit("layers", e.target.value)} />
      </label>
      <button type="button" className="primary" disabled={readOnly} onClick={apply}>Použít</button>
      {error && <p className="code-panel__error" role="alert">{error}</p>}
      {!error && slowMs !== null && <p className="code-panel__slow" role="status">Pomalé vykreslení: {Math.round(slowMs)} ms (limit {SLOW_PAINT_MS} ms).</p>}
    </div>
  );
}
