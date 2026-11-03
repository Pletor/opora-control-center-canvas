import type { TypeGroup, TypeStyle } from "@/project/site-admin/logic/site-document";
import { TokensScope } from "@/project/site-admin/ds-preview/components/TokensScope";
import { sampleCss } from "../logic/typography";

const FIELDS: { key: "fontSize" | "lineHeight" | "fontWeight" | "letterSpacing"; label: string; hint: string }[] = [
  { key: "fontSize", label: "Velikost", hint: "16px" }, { key: "lineHeight", label: "Řádkování", hint: "1.5 nebo 24px" },
  { key: "fontWeight", label: "Váha", hint: "400" }, { key: "letterSpacing", label: "Prostrkání", hint: "-0.01em" },
];

/** Jeden typografický styl: živá ukázka nahoře (třída `.<styl>` z uloženého `tokens.css` a navrch rozepsané hodnoty),
 *  pod ní pole. Prázdné pole se z dokumentu vypustí. */
export default function TypeStyleRow({ style, group, families, theme, onChange, onRemove }: {
  style: TypeStyle; group: TypeGroup; families: string[]; theme: string; onChange: (style: TypeStyle) => void; onRemove: () => void;
}) {
  const set = (key: keyof TypeStyle, value: string) => {
    const next: TypeStyle = { ...style };
    if (value === "" && key !== "fontSize" && key !== "name") delete next[key]; else (next as Record<string, unknown>)[key] = value;
    onChange(next);
  };
  return <div className="ds-type__style" data-testid={"type-style-" + style.name}>
    <TokensScope theme={theme} className="ds-type__preview">
      <p className={"ds-type__sample " + style.name} style={sampleCss(style, group)}>{style.sample || style.name}</p>
    </TokensScope>
    <div className="ds-type__fields">
      <label className="ds-type__field">Jméno<input className="ds-type__input ds-type__input--mono" value={style.name} maxLength={64} spellCheck={false} onChange={(event) => set("name", event.target.value)}/></label>
      {FIELDS.map((field) => <label key={field.key} className="ds-type__field">{field.label}
        <input className="ds-type__input ds-type__input--short" value={style[field.key] === undefined ? "" : String(style[field.key])} placeholder={field.hint} maxLength={24}
          onChange={(event) => set(field.key, event.target.value)}/>
      </label>)}
      <label className="ds-type__field">Řez<select className="ds-type__input" value={style.fontStyle ?? ""} onChange={(event) => set("fontStyle", event.target.value)}>
        <option value="">—</option><option value="normal">normal</option><option value="italic">italic</option></select></label>
      <label className="ds-type__field">Rodina<select className="ds-type__input" value={style.family ?? ""} onChange={(event) => set("family", event.target.value)}>
        <option value="">{group.family ? `jako skupina (${group.family})` : "—"}</option>{families.map((key) => <option key={key} value={key}>{key}</option>)}</select></label>
      <label className="ds-type__field ds-type__field--wide">Ukázka<input className="ds-type__input" value={style.sample ?? ""} maxLength={200} onChange={(event) => set("sample", event.target.value)}/></label>
      <label className="ds-type__field ds-type__field--wide">Kdy použít<input className="ds-type__input" value={style.usage ?? ""} maxLength={1000} onChange={(event) => set("usage", event.target.value)}/></label>
      <button type="button" className="ds-type__remove" aria-label={"Odebrat styl " + style.name} onClick={onRemove}>×</button>
    </div>
  </div>;
}
