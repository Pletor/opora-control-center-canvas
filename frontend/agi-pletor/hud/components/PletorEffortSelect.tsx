import "../styles/pletor-llm.css";

type Props = { levels: string[]; value: string; label: string; className?: string; disabled?: boolean; onChange: (level: string) => void };

/** Výběr effortu (hloubky uvažování) vedle modelu: první položka „výchozí“ (hodnota ""), pak úrovně modelu. Aktuální
 *  hodnota mimo seznam zůstane jako vlastní položka. Dílek nic nezapisuje, volbu hlásí `onChange` ("" = výchozí). */
export default function PletorEffortSelect({ levels, value, label, className = "pletor-llm__model", disabled, onChange }: Props) {
  const known = !value || levels.includes(value);
  return (
    <select className={className} aria-label={label} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
      <option value="">výchozí</option>
      {!known && <option value={value}>{value}</option>}
      {levels.map((level) => <option key={level} value={level}>{level}</option>)}
    </select>
  );
}
