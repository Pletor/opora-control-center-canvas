import { parseSection, type SectionChoice } from "../logic/section-choice";

type Props = {
  choice: SectionChoice;
  /** Člověk vybral sekci stránky; `null` = neurčeno. Ukládá rodič. */
  onSection: (section: string | null) => void;
  disabled?: boolean;
};

/** Výběr „Sekce stránky“: kterou sekci nejbližší stránky komponenta realizuje (`card.section`).
 *  Odkaz na sekci, kterou stránka už nemá, zůstane ve výběru jako „chybí sekce …“, dokud ho člověk nezmění. */
export default function SectionPicker({ choice, onSection, disabled = false }: Props) {
  const { options, value, missing } = choice;
  return (
    <label className="element-detail__section">
      <span className="element-detail__section-label">Sekce stránky</span>
      <select className={`element-detail__section-select${missing ? " element-detail__section-select--missing" : ""}`}
        value={value} disabled={disabled} onChange={(event) => onSection(parseSection(event.target.value))}>
        <option value="">neurčeno</option>
        {missing ? <option value={missing}>chybí sekce {missing}</option> : null}
        {options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
      </select>
    </label>
  );
}
