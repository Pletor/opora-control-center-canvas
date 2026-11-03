import { parseColor, toHex } from "../logic/color-contrast";
import { aliasTarget, type ContrastResult } from "../logic/color-tokens";

/** Hodnota barvy v jednom tématu: výběr „vlastní / alias / dědí“, color picker a text. Vzorek ukazuje barvu po
 *  rozbalení aliasu, odznak kontrast proti dvojici. Hodnotu hlásí nahoru, nic neukládá. */
export default function ColorValueCell({ themeName, first, raw, inherited, resolved, problem, aliases, contrast, onChange }: {
  themeName: string; first: boolean; raw: string; inherited: boolean; resolved: string; problem: string;
  aliases: string[]; contrast: ContrastResult; onChange: (raw: string) => void;
}) {
  const target = aliasTarget(raw);
  const mode = inherited ? "inherit" : target ? "alias:" + target : "value";
  const rgb = parseColor(target ? resolved : raw);
  const choose = (next: string) => {
    if (next === "inherit") onChange("");
    else if (next === "value") onChange(resolved && !target ? resolved : rgb ? toHex(rgb) : "#888888");
    else onChange(`{${next.slice(6)}}`);
  };
  return <div className={"ds-colors__cell" + (problem ? " ds-colors__cell--problem" : "")}>
    <span className="ds-colors__swatch" style={{ background: resolved || "transparent" }} title={problem || resolved} aria-hidden="true"/>
    <div className="ds-colors__cell-edit">
      <select className="ds-colors__mode" aria-label={"Zdroj barvy " + themeName} value={mode} onChange={(event) => choose(event.target.value)}>
        <option value="value">Vlastní barva</option>
        {!first && <option value="inherit">Dědí z výchozího tématu</option>}
        {aliases.map((name) => <option key={name} value={"alias:" + name}>{`{${name}}`}</option>)}
      </select>
      {mode === "value" && <span className="ds-colors__value">
        <input type="color" className="ds-colors__picker" aria-label={"Barva " + themeName} value={rgb ? toHex(rgb) : "#888888"} onChange={(event) => onChange(event.target.value)}/>
        <input className="ds-colors__text" aria-label={"Hodnota " + themeName} value={raw} maxLength={120} spellCheck={false} onChange={(event) => onChange(event.target.value)}/>
      </span>}
      {mode !== "value" && <small className="ds-colors__resolved">{problem || resolved}</small>}
    </div>
    {contrast && <span className={"ds-colors__badge ds-colors__badge--" + contrast.level} title={`Kontrast ${contrast.ratio.toFixed(2)}:1 proti ${contrast.pair}`}>
      {contrast.level === "fail" ? "✕" : contrast.level} {contrast.ratio.toFixed(1)} · {contrast.pair}
    </span>}
  </div>;
}
