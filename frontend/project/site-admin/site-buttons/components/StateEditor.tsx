import { ColorField, Segments, TextField } from "@/project/site-admin/site-fields/components/Fields";
import { isGradient, toggleGradient } from "../logic/button-gradient";
import { effective, withNestedKey, withStateKey, type ButtonState, type StateName, type Variant } from "../logic/button-model";
import GradientEditor from "./GradientEditor";
import StateDetails from "./StateDetails";

const RADII = [{ value: "none", label: "▢ 0" }, { value: "sm", label: "◜ sm" }, { value: "md", label: "◜ md" }, { value: "lg", label: "◠ lg" }, { value: "pill", label: "⬭ pill" }];
const WIDTHS = [{ value: "auto", label: "Podle textu" }, { value: "full", label: "Na celou šířku" }];

/** Pole jednoho stavu podle `image.png`: pozadí s přepínačem „Barevný přechod“, barva písma, zaoblení rohů
 *  (předvolby a vlastní), šířka a stín; pod nimi font, rámeček, focus ring a přechod. Mimo výchozí stav je prázdné
 *  pole zděděné z „Tlačítko“ a zděděná hodnota je v placeholderu. */
export default function StateEditor({ variant, state, aliases, families, onChange }: {
  variant: Variant; state: StateName; aliases: string[]; families: string[]; onChange: (variant: Variant) => void;
}) {
  const own = variant.states[state] ?? {};
  const inherited = state === "default" ? {} : effective(variant, "default");
  const background = own.background ?? (isGradient(inherited.background) ? undefined : inherited.background);
  const gradient = isGradient(own.background) ? own.background : null;
  const radius = own.radius ?? "";
  const custom = radius && !RADII.some((option) => option.value === radius) ? radius : "";
  return <div className="site-buttons__fields" data-testid={"button-state-" + state}>
    <ColorField label="Pozadí tlačítka" value={gradient ? "" : own.background as string ?? ""} placeholder={gradient ? "barevný přechod níže" : typeof inherited.background === "string" ? inherited.background : "zděděné"}
      aliases={aliases} onChange={(value) => onChange(withStateKey(variant, state, "background", value))}>
      <label className="site-buttons__toggle">
        <input type="checkbox" checked={!!gradient} onChange={(event) => onChange(withStateKey(variant, state, "background", toggleGradient(gradient ?? (background as string), event.target.checked)))}/>
        Barevný přechod
      </label>
    </ColorField>
    <ColorField label="Barva písma" value={own.color ?? ""} placeholder={inherited.color ?? "currentColor"} aliases={aliases}
      onChange={(value) => onChange(withStateKey(variant, state, "color", value))}/>
    <Segments label="Šířka" value={own.width ?? ""} options={WIDTHS} onChange={(value) => onChange(withStateKey(variant, state, "width", (value || undefined) as ButtonState["width"]))}/>
    {gradient && <div className="site-fields__field--wide"><GradientEditor value={gradient} aliases={aliases} onChange={(value) => onChange(withStateKey(variant, state, "background", value))}/></div>}
    <Segments label="Zaoblení rohů" value={custom ? "" : radius} options={RADII} onChange={(value) => onChange(withStateKey(variant, state, "radius", value))}/>
    <TextField label="Vlastní zaoblení" value={custom} placeholder={inherited.radius ?? "např. 12px nebo {radius-md}"} mono
      onChange={(value) => onChange(withStateKey(variant, state, "radius", value))}/>
    <TextField label="Stín" value={own.shadow ?? ""} placeholder={inherited.shadow ?? "none, 0 2px 6px rgba(0,0,0,.2) nebo {shadow-sm}"} mono
      onChange={(value) => onChange(withStateKey(variant, state, "shadow", value))}/>
    <StateDetails own={own} inherited={inherited} state={state} aliases={aliases} families={families}
      onNested={(key, field, value) => onChange(withNestedKey(variant, state, key, field, value))}/>
  </div>;
}
