import { useEffect, useState } from "react";
import type { StudioModelNode } from "../../model/logic/model-types";
import { parseParameter, type ParameterRow } from "../logic/inspector-fields";

/** Jeden parametr simulace: popisek s mezemi, číselné pole (nebo výběr u výčtu) s výchozí hodnotou jako nápovědou.
 * Číslo se zapíše po opuštění pole nebo Enteru, aby rozepsané „12,“ nezmizelo; neplatná hodnota zůstane v poli
 * s hláškou pod ním a do modelu se nedostane. Undo / redo pole srovná s modelem. */
export default function ParameterField({ node, row, onChange }: { node: StudioModelNode; row: ParameterRow; onChange: (value: number | string | undefined) => void }) {
  const shown = row.value === undefined ? "" : String(row.value);
  const [draft, setDraft] = useState(shown);
  const [error, setError] = useState("");
  useEffect(() => { setDraft(shown); setError(""); }, [shown]);
  const commit = (raw: string) => {
    const parsed = parseParameter(node, row, raw);
    if ("error" in parsed) { setError(parsed.error); return; }
    setError("");
    if (parsed.value !== row.value) onChange(parsed.value);
  };
  const bounds = row.min !== undefined || row.max !== undefined ? ` (${row.min ?? "…"}–${row.max ?? "…"})` : "";
  return <label className="studio-model-inspector__field studio-model-inspector__field--parameter" data-testid={"studio-model-param-" + row.key}>
    <span className="studio-model-inspector__label">{row.label}<small className="studio-model-inspector__bounds">{bounds}</small></span>
    {row.options
      ? <select className="studio-model-inspector__input" value={shown} onChange={(event) => commit(event.target.value)}>
          <option value="">výchozí ({row.fallback})</option>
          {row.options.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      : <input className={"studio-model-inspector__input" + (error ? " studio-model-inspector__input--invalid" : "")} inputMode="decimal" value={draft}
          placeholder={row.fallback} aria-invalid={!!error} onChange={(event) => setDraft(event.target.value)}
          onBlur={() => commit(draft)} onKeyDown={(event) => { if (event.key === "Enter") commit(draft); if (event.key === "Escape") { setDraft(shown); setError(""); } }}/>}
    {error && <small className="studio-model-inspector__error" role="alert">{error}</small>}
  </label>;
}
