import "../styles/pletor-llm.css";
import type { LlmModel } from "../logic/llm-settings";

type Props = {
  models: LlmModel[]; value: string; label: string; emptyLabel?: string; className?: string; disabled?: boolean;
  onChange: (id: string) => void;
};

/** Výběr modelu ze seznamu: aktuální je označený i tehdy, když v seznamu není (zůstane jako vlastní položka);
 *  prázdná hodnota ukáže `emptyLabel` (např. výchozí z Codexu). Dílek nic nezapisuje, volbu hlásí `onChange`. */
export default function PletorLlmModelSelect({ models, value, label, emptyLabel, className = "pletor-llm__model", disabled, onChange }: Props) {
  const known = !value || models.some((m) => m.id === value);
  return (
    <select className={className} aria-label={label} value={value} disabled={disabled} onChange={(event) => event.target.value && onChange(event.target.value)}>
      {!value && <option value="">{emptyLabel ?? "výchozí"}</option>}
      {!known && <option value={value}>{value}</option>}
      {models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
    </select>
  );
}
