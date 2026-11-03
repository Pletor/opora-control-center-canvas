import { ColorField, SelectField, TextField } from "@/project/site-admin/site-fields/components/Fields";
import { numberLeaf, type Appearance, type Leaf } from "../logic/appearance";

const options = (...values: string[]) => values.map((value) => ({ value, label: value }));
const text = (value: Leaf) => value === null ? "" : String(value);

/** Pozadí stránky: barva, obrázek z assetů, vzorek a překryv. Každé pole je jeden token webu. */
export default function BackgroundEditor({ appearance, aliases, assets, onField }: {
  appearance: Appearance; aliases: string[]; assets: string[]; onField: (path: string, value: Leaf) => void;
}) {
  const { color, image, pattern, overlay } = appearance.background;
  return <fieldset className="site-appearance__group">
    <legend className="site-appearance__legend">Pozadí</legend>
    <div className="site-appearance__grid">
      <ColorField label="Barva pozadí" value={text(color)} placeholder="token surface" aliases={aliases} onChange={(value) => onField("background.color", value)}/>
      <SelectField label="Obrázek" value={text(image.asset)} empty={assets.length ? "Bez obrázku" : "Žádný obrázek v Assets"}
        options={assets.map((value) => ({ value, label: value.replace(/^assets\//, "") }))} onChange={(value) => onField("background.image.asset", value)}/>
      <SelectField label="Velikost obrázku" value={text(image.size)} empty="cover" options={options("cover", "contain", "auto")} onChange={(value) => onField("background.image.size", value)}/>
      <SelectField label="Poloha obrázku" value={text(image.position)} empty="center"
        options={options("center", "top", "bottom", "left", "right", "top left", "top right", "bottom left", "bottom right")}
        onChange={(value) => onField("background.image.position", value)}/>
      <SelectField label="Opakování" value={text(image.repeat)} empty="no-repeat" options={options("no-repeat", "repeat", "repeat-x", "repeat-y")}
        onChange={(value) => onField("background.image.repeat", value)}/>
      <SelectField label="Při posunu" value={text(image.attachment)} empty="scroll" options={[{ value: "scroll", label: "posouvá se (scroll)" }, { value: "fixed", label: "stojí (fixed)" }]}
        onChange={(value) => onField("background.image.attachment", value)}/>
      <SelectField label="Vzorek" value={text(pattern.preset)} empty="Bez vzorku"
        options={[{ value: "dots", label: "Tečky" }, { value: "grid", label: "Mřížka" }, { value: "lines", label: "Linky" }, { value: "diagonal", label: "Šikmé čáry" }]}
        onChange={(value) => onField("background.pattern.preset", value)}/>
      <ColorField label="Barva vzorku" value={text(pattern.color)} placeholder="currentColor" aliases={aliases} onChange={(value) => onField("background.pattern.color", value)}/>
      <TextField label="Měřítko vzorku" value={text(pattern.scale)} placeholder="1" hint="0,25–8, buňka 16 px × měřítko"
        onChange={(value) => onField("background.pattern.scale", numberLeaf(value))}/>
      <ColorField label="Překryv" value={text(overlay.color)} placeholder="bez překryvu" aliases={aliases} onChange={(value) => onField("background.overlay.color", value)}/>
      <TextField label="Krytí překryvu" value={text(overlay.opacity)} placeholder="1" hint="0–1" onChange={(value) => onField("background.overlay.opacity", numberLeaf(value))}/>
    </div>
  </fieldset>;
}
