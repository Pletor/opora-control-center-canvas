import { useState } from "react";
import { withThemeValue, type ScaleKind, type Theme, type Token } from "@/project/site-admin/logic/site-document";
import { nameProblem } from "@/project/site-admin/logic/token-names";
import { TokensScope } from "@/project/site-admin/ds-preview/components/TokensScope";
import { scaleSwatch } from "../logic/scale-tokens";

/** Jeden token rodiny: jméno, hodnota (u stínu jedna na každé téma), usage a ukázka. Ukázka stínu stojí v náhledu
 *  tokenů projektu (`.ds-scope`) v tom tématu, pro které hodnota platí. */
export default function ScaleTokenRow({ kind, token, themes, taken, onChange, onRemove }: {
  kind: ScaleKind; token: Token; themes: Theme[]; taken: string[]; onChange: (token: Token) => void; onRemove: () => void;
}) {
  const [name, setName] = useState(token.name);
  const problem = name === token.name ? "" : nameProblem(name, taken, token.name);
  const first = themes[0]?.id ?? "light";
  const commit = () => { if (name !== token.name && !problem) onChange({ ...token, name }); else setName(token.name); };
  const values = kind === "shadow" ? themes : themes.slice(0, 1);
  return <div className="ds-scale__row" data-testid={`scale-${kind}-${token.name}`}>
    <label className="ds-scale__name">
      <input className={"ds-scale__input ds-scale__input--mono" + (problem ? " ds-scale__input--problem" : "")} aria-label="Jméno tokenu" value={name} maxLength={64} spellCheck={false}
        onChange={(event) => setName(event.target.value)} onBlur={commit} onKeyDown={(event) => { if (event.key === "Enter") commit(); }}/>
      <code className="ds-scale__var">{problem || `var(--${token.name})`}</code>
    </label>
    <div className="ds-scale__values">
      {values.map((theme) => {
        const raw = typeof token.value === "string" ? (theme.id === first ? token.value : "") : token.value[theme.id] ?? "";
        return <div key={theme.id} className="ds-scale__value">
          <input className="ds-scale__input ds-scale__input--mono" aria-label={kind === "shadow" ? `Stín ${theme.name}` : "Hodnota"} value={raw} maxLength={400} spellCheck={false}
            placeholder={theme.id === first ? (kind === "shadow" ? "0 1px 2px rgba(0,0,0,.1)" : "16px") : "dědí z výchozího"}
            onChange={(event) => onChange({ ...token, value: kind === "shadow" ? withThemeValue(token.value, theme.id, event.target.value, themes) : event.target.value })}/>
          <TokensScope theme={theme.id} className={"ds-scale__preview ds-scale__preview--" + kind}>
            <span className={"ds-scale__swatch ds-scale__swatch--" + kind} style={scaleSwatch(kind, token, theme.id, first)}/>
            {kind === "shadow" && <small className="ds-scale__theme">{theme.name}</small>}
          </TokensScope>
        </div>;
      })}
    </div>
    <textarea className="ds-scale__input ds-scale__usage" aria-label="Kdy token použít" rows={2} maxLength={1000} placeholder="Kdy ho použít" value={token.usage ?? ""}
      onChange={(event) => onChange({ ...token, usage: event.target.value || undefined })}/>
    <button type="button" className="ds-scale__remove" aria-label={"Odebrat " + token.name} onClick={onRemove}>×</button>
  </div>;
}
