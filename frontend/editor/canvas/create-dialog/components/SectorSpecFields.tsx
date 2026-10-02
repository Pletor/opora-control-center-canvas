// Zadání sektoru při jeho vzniku: cíl, co nedělat a kdy je hotovo. Jsou to tatáž tři pole, která
// později upravuje záložka Zadání (`NodeSpecEditor`); uloží je rodič přes existující spec API.
// Pop-up je balí do sbalitelné sekce „Zadání sektoru (nepovinné)“, proto tu už „nepovinné“ nestojí.
import type { SpecFields } from "@/shared/types/logic/types";

const FIELDS: { key: keyof SpecFields; label: string; limit: number }[] = [
  { key: "goal", label: "Cíl", limit: 4000 },
  { key: "non_goals", label: "Co nedělat", limit: 8000 },
  { key: "acceptance", label: "Hotovo, když", limit: 12000 },
];

export default function SectorSpecFields({ value, onChange }: { value: SpecFields; onChange: (next: SpecFields) => void }) {
  return (
    <div className="create-dialog__spec" role="group" aria-label="Zadání sektoru">
      {FIELDS.map((field) => (
        <label key={field.key} className="field">
          {field.label}
          <textarea
            aria-label={field.label}
            rows={2}
            maxLength={field.limit}
            value={value[field.key]}
            onChange={(e) => onChange({ ...value, [field.key]: e.target.value })}
          />
        </label>
      ))}
    </div>
  );
}
