import { SIZES, withSize, type Buttons, type Size } from "../logic/button-model";

const FIELDS: { key: keyof Size; label: string }[] = [
  { key: "minHeight", label: "Výška (min-height)" }, { key: "paddingY", label: "Vnitřní okraj svisle" },
  { key: "paddingX", label: "Vnitřní okraj vodorovně" }, { key: "fontSize", label: "Velikost písma" },
];

/** Výška a šířka tlačítek jako škála sm / md / lg, společná všem variantám (`ds-btn--sm|md|lg`). */
export default function SizesEditor({ buttons, onChange }: { buttons: Buttons; onChange: (buttons: Buttons) => void }) {
  return <fieldset className="site-buttons__group">
    <legend className="site-buttons__legend">Výška a šířka (škála velikostí)</legend>
    <table className="site-buttons__sizes">
      <thead><tr><th className="site-buttons__th">Pole</th>{SIZES.map((size) => <th key={size} className="site-buttons__th">{size}</th>)}</tr></thead>
      <tbody>{FIELDS.map((field) => <tr key={field.key}>
        <th scope="row" className="site-buttons__th">{field.label}</th>
        {SIZES.map((size) => <td key={size} className="site-buttons__td">
          <input className="site-fields__input site-fields__input--mono site-buttons__size-input" aria-label={`${size} ${field.label}`}
            value={buttons.sizes[size][field.key]} maxLength={40} onChange={(event) => onChange(withSize(buttons, size, field.key, event.target.value))}/>
        </td>)}
      </tr>)}</tbody>
    </table>
    <p className="site-buttons__hint">Délka (px, rem, em, %) nebo token, např. <code>{"{space-4}"}</code>. Výška pod 24 px nesplní WCAG 2.5.8; server to při uložení řekne.</p>
  </fieldset>;
}
