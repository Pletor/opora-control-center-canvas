// Výběr karty pro Storyboard: roletka karet prostoru; karty, o kterých už se ví, že storyboard mají, jsou označené
// tečkou. Dílek nic nenačítá, jen hlásí zvolenou kartu.
import type { PickerCard } from "../logic/storyboard-layout";

export default function CardPicker({ cards, value, marks, onChange }: {
  cards: PickerCard[];
  value: string | null;
  /** Karty, u kterých je známo, že storyboard mají (true) nebo nemají (false); neznámé chybí. */
  marks: Record<string, boolean>;
  onChange: (id: string) => void;
}) {
  return (
    <label className="storyboard__picker">Karta
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        {value === null && <option value="" disabled>Vyberte kartu…</option>}
        {cards.map((c) => <option key={c.id} value={c.id}>{marks[c.id] ? "● " : ""}{c.name}</option>)}
      </select>
    </label>
  );
}
