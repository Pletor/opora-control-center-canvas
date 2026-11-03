import { useState } from "react";
import type { SiteInvalid } from "@/project/site-admin/logic/site-admin-api";
import { SelectField, TextField } from "@/project/site-admin/site-fields/components/Fields";
import { addVariant, PRESET_VARIANTS, PRESETS, readButtons, readCustomCss, removeVariant, STATES, variantNotes, withVariant,
  type Buttons, type Preset, type StateName } from "../logic/button-model";
import VariantList from "./VariantList";
import ButtonsPreview from "./ButtonsPreview";
import StateEditor from "./StateEditor";
import SizesEditor from "./SizesEditor";
import CustomCssEditor from "./CustomCssEditor";
import "../styles/site-buttons.css";

export type ButtonsChange = { buttons: Buttons; customCss: Record<string, string> };
const PRESET_LABEL: Record<Preset, string> = { solid: "Plné (solid)", outline: "Obrys (outline)", ghost: "Bez pozadí (ghost)", link: "Jako odkaz (link)" };

/** Tlačítka webu podle `image.png`: varianty, náhled, styl varianty, záložky stavů s poli, vlastní CSS s animací
 *  a škála velikostí. Dostane `settings` dokumentu, změnu hlásí jako `{buttons, customCss}`; ukládá rodič. */
export default function ButtonsSection({ settings, project, theme, componentsCss, notes, invalid, aliases, families, onChange }: {
  settings: Record<string, unknown>; project: string; theme: string; componentsCss: string; notes: string[]; invalid: SiteInvalid | null;
  aliases: string[]; families: string[]; onChange: (change: ButtonsChange) => void;
}) {
  const buttons = readButtons(settings);
  const customCss = readCustomCss(settings);
  const slugs = Object.keys(buttons.variants);
  const [chosen, setChosen] = useState("");
  const [state, setState] = useState<StateName>("default");
  const [text, setText] = useState("");
  const [still, setStill] = useState(false);
  const slug = buttons.variants[chosen] ? chosen : invalid?.path.match(/customCss\.button\.([a-z0-9-]+)/)?.[1] ?? slugs[0] ?? "";
  const variant = buttons.variants[slug];
  const emit = (next: Buttons, css = customCss) => onChange({ buttons: next, customCss: css });
  const add = (name: string) => { emit(addVariant(buttons, name)); setChosen(name); };
  const addAll = () => { emit(Object.keys(PRESET_VARIANTS).reduce((all, name) => all.variants[name] ? all : addVariant(all, name), buttons)); setChosen("primary"); };
  const remove = (name: string) => { const { [name]: _gone, ...css } = customCss; emit(removeVariant(buttons, name), css); };
  const setCss = (value: string) => { const { [slug]: _old, ...rest } = customCss; emit(buttons, value.trim() ? { ...rest, [slug]: value } : rest); };
  return <div className="site-buttons">
    <VariantList buttons={buttons} selected={slug} onSelect={setChosen} onAdd={add} onAddAll={addAll} onRemove={remove}/>
    {variant && <div className="site-buttons__editor">
      <div className="site-buttons__top">
        <ButtonsPreview project={project} theme={theme} componentsCss={componentsCss} buttons={buttons} customCss={customCss} slug={slug} state={state}
          text={text} still={still} onText={setText} onStill={setStill}/>
        <div className="site-buttons__meta">
          <SelectField label="Styl tlačítka" value={variant.preset} empty="Plné (solid)" options={PRESETS.filter((preset) => preset !== "solid").map((value) => ({ value, label: PRESET_LABEL[value] }))}
            hint="Předvolba říká AI, jak tlačítko použít; vzhled nastavují pole stavů." onChange={(value) => emit(withVariant(buttons, slug, { ...variant, preset: (value || "solid") as Preset }))}/>
          <TextField label="Název varianty" value={variant.label ?? ""} placeholder={slug} onChange={(value) => emit(withVariant(buttons, slug, { ...variant, label: value.trim() ? value : undefined }))}/>
        </div>
      </div>
      <div className="site-buttons__tabs" role="tablist" aria-label="Stavy tlačítka">
        {STATES.map((item) => <button key={item.id} type="button" role="tab" aria-selected={item.id === state}
          className={"site-buttons__tab" + (item.id === state ? " site-buttons__tab--on" : "")} onClick={() => setState(item.id)}>{item.label}</button>)}
      </div>
      <div className="site-buttons__panel" role="tabpanel">
        {state !== "default" && <p className="site-buttons__hint">Prázdné pole dědí ze záložky Tlačítko (šedá hodnota). Uloží se jen rozdíl.</p>}
        <StateEditor variant={variant} state={state} aliases={aliases} families={families} onChange={(next) => emit(withVariant(buttons, slug, next))}/>
      </div>
      <CustomCssEditor slug={slug} project={project} value={customCss[slug] ?? ""} invalid={invalid} notes={variantNotes(notes, slug)} onChange={setCss}/>
    </div>}
    <SizesEditor buttons={buttons} onChange={(next) => emit(next)}/>
  </div>;
}
