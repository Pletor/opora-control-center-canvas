import { ColorField, SelectField, TextField } from "@/project/site-admin/site-fields/components/Fields";
import { LEVELS, numberLeaf, type Appearance, type Leaf } from "../logic/appearance";

const text = (value: Leaf) => value === null ? "" : String(value);
const MARKERS = [["disc", "• plná tečka"], ["circle", "○ kroužek"], ["square", "▪ čtvereček"], ["decimal", "1. čísla"],
  ["decimal-leading-zero", "01. čísla s nulou"], ["lower-alpha", "a. písmena"], ["upper-alpha", "A. písmena"],
  ["lower-roman", "i. římská"], ["upper-roman", "I. římská"], ["none", "bez odrážky"]].map(([value, label]) => ({ value, label }));
const PLACEHOLDER = { h1: "2.5rem", h2: "2rem", h3: "1.5rem", h4: "1.25rem", h5: "1.125rem", h6: "1rem" };

/** Nadpisy H1–H6 jako tabulka (velikost, váha, řádkování, prostrkání) a styl odrážek seznamů. */
export default function HeadingsEditor({ appearance, aliases, onField }: {
  appearance: Appearance; aliases: string[]; onField: (path: string, value: Leaf) => void;
}) {
  const { headings, lists } = appearance;
  const cell = (path: string, value: Leaf, label: string, placeholder: string, parse?: (text: string) => Leaf) =>
    <input className="site-fields__input site-appearance__cell" aria-label={label} value={text(value)} placeholder={placeholder} maxLength={40}
      onChange={(event) => onField(path, parse ? parse(event.target.value) : event.target.value)}/>;
  return <>
    <fieldset className="site-appearance__group">
      <legend className="site-appearance__legend">Nadpisy H1–H6</legend>
      <table className="site-appearance__table">
        <thead><tr>{["Úroveň", "Velikost", "Váha", "Řádkování", "Prostrkání"].map((name) => <th key={name} className="site-appearance__th">{name}</th>)}</tr></thead>
        <tbody>{LEVELS.map((level) => <tr key={level}>
          <th scope="row" className="site-appearance__level">{level.toUpperCase()}</th>
          <td className="site-appearance__td">{cell(`headings.${level}.size`, headings[level].size, `${level} velikost`, PLACEHOLDER[level])}</td>
          <td className="site-appearance__td">{cell(`headings.${level}.weight`, headings[level].weight, `${level} váha`, "700", numberLeaf)}</td>
          <td className="site-appearance__td">{cell(`headings.${level}.lineHeight`, headings[level].lineHeight, `${level} řádkování`, "1.2", (value) => numberLeaf(value) ?? value)}</td>
          <td className="site-appearance__td">{cell(`headings.${level}.letterSpacing`, headings[level].letterSpacing, `${level} prostrkání`, "0")}</td>
        </tr>)}</tbody>
      </table>
    </fieldset>
    <fieldset className="site-appearance__group">
      <legend className="site-appearance__legend">Odrážky</legend>
      <div className="site-appearance__grid">
        <SelectField label="Styl odrážek" value={text(lists.marker)} empty="výchozí prohlížeče" options={MARKERS} onChange={(value) => onField("lists.marker", value)}/>
        <ColorField label="Barva odrážek" value={text(lists.color)} placeholder="jako text" aliases={aliases} onChange={(value) => onField("lists.color", value)}/>
        <TextField label="Odsazení seznamu" value={text(lists.indent)} placeholder="1.5rem" onChange={(value) => onField("lists.indent", value)}/>
      </div>
    </fieldset>
  </>;
}
