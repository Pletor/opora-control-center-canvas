import { useState } from "react";
import { withThemeValue, type ColorFamily, type Token } from "@/project/site-admin/logic/site-document";
import { nameProblem } from "@/project/site-admin/logic/token-names";
import { resolveColor, tokenContrast } from "../logic/color-tokens";
import ColorValueCell from "./ColorValueCell";

/** Šablona mřížky řádku: jméno, sloupec na každé téma, usage, odebrat. Sdílí ji hlavička tabulky. */
export const rowColumns = (themes: number) => `minmax(150px, 1fr) repeat(${themes}, minmax(190px, 1.2fr)) minmax(180px, 1.4fr) 24px`;

/** Jedna barva: jméno, hodnota pro každé téma, usage a kontrast. Jméno se potvrdí až opuštěním pole, aby se při
 *  psaní nepřepisovaly aliasy na půl napsané jméno. */
export default function ColorTokenRow({ family, token, taken, onChange, onRename, onRemove }: {
  family: ColorFamily; token: Token; taken: string[];
  onChange: (token: Token) => void; onRename: (name: string) => void; onRemove: () => void;
}) {
  const [name, setName] = useState(token.name);
  const problem = name === token.name ? "" : nameProblem(name, taken, token.name);
  const first = family.themes[0].id;
  const aliases = family.tokens.map((item) => item.name).filter((item) => item !== token.name);
  const commit = () => { if (name !== token.name && !problem) onRename(name); else setName(token.name); };
  return <div className="ds-colors__row" data-testid={"color-token-" + token.name} style={{ gridTemplateColumns: rowColumns(family.themes.length) }}>
    <label className="ds-colors__name">
      <input className={"ds-colors__name-input" + (problem ? " ds-colors__name-input--problem" : "")} aria-label="Jméno barvy" value={name} maxLength={64} spellCheck={false}
        onChange={(event) => setName(event.target.value)} onBlur={commit} onKeyDown={(event) => { if (event.key === "Enter") commit(); }}/>
      <code className="ds-colors__var">{problem || `var(--${token.name})`}</code>
    </label>
    {family.themes.map((theme) => {
      const raw = typeof token.value === "string" ? (theme.id === first ? token.value : "") : token.value[theme.id] ?? "";
      const resolved = resolveColor(family.tokens, token.name, theme.id, first);
      return <ColorValueCell key={theme.id} themeName={theme.name} first={theme.id === first} raw={raw} inherited={!raw && theme.id !== first}
        resolved={"value" in resolved ? resolved.value : ""} problem={"error" in resolved ? resolved.error : ""} aliases={aliases}
        contrast={tokenContrast(family, token.name, theme.id)}
        onChange={(next) => onChange({ ...token, value: withThemeValue(token.value, theme.id, next, family.themes) })}/>;
    })}
    <textarea className="ds-colors__usage" aria-label="Kdy barvu použít" rows={2} maxLength={1000} placeholder="Kdy ji použít (text na surface…)" value={token.usage ?? ""}
      onChange={(event) => onChange({ ...token, usage: event.target.value || undefined })}/>
    <button type="button" className="ds-colors__icon" aria-label={"Odebrat barvu " + token.name} onClick={onRemove}>×</button>
  </div>;
}
