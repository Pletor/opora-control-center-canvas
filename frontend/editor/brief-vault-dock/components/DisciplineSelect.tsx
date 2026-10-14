// Seskupený výběr disciplíny (Kreslení · Logika · Provoz) pro Nové zadání a Podnět → fragment. Jen zobrazení;
// volbu hlásí callbackem.
import { DISCIPLINES, GROUPS } from "../logic/disciplines";

export default function DisciplineSelect({ value, label, placeholder, onChange }: {
  /** Id disciplíny, nebo `""` = nic nevybráno. */
  value: string;
  label: string;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  return (
    <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">{placeholder}</option>
      {GROUPS.map((group) => (
        <optgroup key={group.id} label={group.label}>
          {DISCIPLINES.filter((item) => item.group === group.id).map((item) => (
            <option key={item.id} value={item.id}>{item.label}</option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
