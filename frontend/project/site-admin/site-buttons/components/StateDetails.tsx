import { ColorField, SelectField, TextField } from "@/project/site-admin/site-fields/components/Fields";
import type { ButtonState, StateName } from "../logic/button-model";

type Key = "border" | "font" | "transition" | "outline";
type Value = string | number | string[] | undefined;
const list = (...values: string[]) => values.map((value) => ({ value, label: value }));
const WEIGHTS = list("300", "400", "500", "600", "700", "800", "900");
const STYLES = list("solid", "dashed", "dotted", "double", "none");
const TRANSFORMS = [{ value: "none", label: "beze změny" }, { value: "uppercase", label: "VERZÁLKY" }, { value: "lowercase", label: "minusky" }, { value: "capitalize", label: "Velká Počáteční" }];
const EASING = list("ease", "ease-in", "ease-out", "ease-in-out", "linear", "cubic-bezier(0.2, 0.8, 0.2, 1)");
const MOTION = ["background-color", "color", "border-color", "box-shadow", "transform", "opacity", "outline-color", "all"];

/** Font, rámeček, focus ring (jen ve stavu Focus) a přechod jednoho stavu. Vnořené objekty mění pole po poli. */
export default function StateDetails({ own, inherited, state, aliases, families, onNested }: {
  own: ButtonState; inherited: ButtonState; state: StateName; aliases: string[]; families: string[];
  onNested: (key: Key, field: string, value: Value) => void;
}) {
  const get = (key: Key, field: string) => String(own[key]?.[field] ?? "");
  const hint = (key: Key, field: string, fallback: string) => String(inherited[key]?.[field] ?? fallback);
  const by = (key: Key, field: string, fallback: string) => "výchozí: " + hint(key, field, fallback);
  const properties = (own.transition?.properties ?? inherited.transition?.properties ?? []) as string[];
  const toggle = (property: string, on: boolean) => onNested("transition", "properties", on ? [...properties, property] : properties.filter((item) => item !== property));
  return <>
    <h4 className="site-buttons__subhead">Font tlačítka</h4>
    <SelectField label="Rodina písma" value={get("font", "family")} empty={families.length ? by("font", "family", "jako okolní text") : "Žádné rodiny v Typography"}
      options={families.map((value) => ({ value, label: `${value} (--font-${value})` }))} onChange={(value) => onNested("font", "family", value)}/>
    <SelectField label="Váha" value={get("font", "weight")} empty={by("font", "weight", "600")} options={WEIGHTS}
      onChange={(value) => onNested("font", "weight", value ? Number(value) : undefined)}/>
    <TextField label="Prostrkání" value={get("font", "letterSpacing")} placeholder={hint("font", "letterSpacing", "normal")} mono onChange={(value) => onNested("font", "letterSpacing", value)}/>
    <SelectField label="Velikost písmen" value={get("font", "transform")} empty={by("font", "transform", "beze změny")} options={TRANSFORMS}
      onChange={(value) => onNested("font", "transform", value)}/>

    <h4 className="site-buttons__subhead">Rámeček</h4>
    <TextField label="Šířka rámečku" value={get("border", "width")} placeholder={hint("border", "width", "0")} mono onChange={(value) => onNested("border", "width", value)}/>
    <SelectField label="Styl rámečku" value={get("border", "style")} empty={by("border", "style", "solid")} options={STYLES} onChange={(value) => onNested("border", "style", value)}/>
    <ColorField label="Barva rámečku" value={get("border", "color")} placeholder={hint("border", "color", "transparent")} aliases={aliases} onChange={(value) => onNested("border", "color", value)}/>

    {state === "focusVisible" && <>
      <h4 className="site-buttons__subhead">Focus ring (obrys při ovládání klávesnicí)</h4>
      <TextField label="Šířka obrysu" value={get("outline", "width")} placeholder="2px" mono onChange={(value) => onNested("outline", "width", value)}/>
      <SelectField label="Styl obrysu" value={get("outline", "style")} empty="výchozí: solid" options={STYLES} onChange={(value) => onNested("outline", "style", value)}/>
      <ColorField label="Barva obrysu" value={get("outline", "color")} placeholder="token focus" aliases={aliases} onChange={(value) => onNested("outline", "color", value)}/>
      <TextField label="Odsazení obrysu" value={get("outline", "offset")} placeholder="2px" mono onChange={(value) => onNested("outline", "offset", value)}/>
    </>}

    <h4 className="site-buttons__subhead">Přechod (transition)</h4>
    <div className="site-buttons__motion site-fields__field--wide" role="group" aria-label="Co se animuje">
      {MOTION.map((property) => <label key={property} className="site-buttons__check">
        <input type="checkbox" checked={properties.includes(property)} onChange={(event) => toggle(property, event.target.checked)}/>{property}
      </label>)}
    </div>
    <TextField label="Délka" value={get("transition", "duration")} placeholder={hint("transition", "duration", "150ms")} mono onChange={(value) => onNested("transition", "duration", value)}/>
    <SelectField label="Průběh" value={get("transition", "easing")} empty={by("transition", "easing", "ease")} options={EASING} onChange={(value) => onNested("transition", "easing", value)}/>
  </>;
}
