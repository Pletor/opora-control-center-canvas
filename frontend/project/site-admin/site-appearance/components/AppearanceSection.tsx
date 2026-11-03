import { useMemo } from "react";
import { TextField } from "@/project/site-admin/site-fields/components/Fields";
import { readAppearance, withField, type Appearance, type Leaf } from "../logic/appearance";
import { appearanceCss } from "../logic/appearance-css";
import BackgroundEditor from "./BackgroundEditor";
import TextEditor from "./TextEditor";
import HeadingsEditor from "./HeadingsEditor";
import AppearancePreview from "./AppearancePreview";
import "../styles/site-appearance.css";

const text = (value: Leaf) => value === null ? "" : String(value);

/** Vzhled webu: pozadí, písmo, barvy textu, nadpisy, odrážky a pokročilá šířka stránky, vedle živý náhled.
 *  Dostane `settings` dokumentu a celý nový Vzhled hlásí nahoru; ukládá rodič. */
export default function AppearanceSection({ settings, project, theme, aliases, stacks, assets, onChange }: {
  settings: Record<string, unknown>; project: string; theme: string; aliases: string[]; stacks: string[]; assets: string[];
  onChange: (appearance: Appearance) => void;
}) {
  const appearance = readAppearance(settings);
  const css = useMemo(() => appearanceCss(appearance, project), [appearance, project]);
  const onField = (path: string, value: Leaf) => onChange(withField(appearance, path, value));
  const { layout } = appearance;
  return <div className="site-appearance">
    <div className="site-appearance__form">
      <BackgroundEditor appearance={appearance} aliases={aliases} assets={assets} onField={onField}/>
      <TextEditor appearance={appearance} aliases={aliases} stacks={stacks} onField={onField}/>
      <HeadingsEditor appearance={appearance} aliases={aliases} onField={onField}/>
      <details className="site-appearance__advanced">
        <summary className="site-appearance__summary">Pokročilé: šířka stránky</summary>
        <div className="site-appearance__grid">
          <TextField label="Šířka obsahu" value={text(layout.contentSize)} placeholder="720px" hint="max-width .ds-container" onChange={(value) => onField("layout.contentSize", value)}/>
          <TextField label="Široký obsah" value={text(layout.wideSize)} placeholder="1200px" hint=".ds-container--wide" onChange={(value) => onField("layout.wideSize", value)}/>
          <TextField label="Okraj stránky" value={text(layout.gutter)} placeholder="1.5rem" hint="padding-inline kontejneru" onChange={(value) => onField("layout.gutter", value)}/>
        </div>
      </details>
    </div>
    <AppearancePreview css={css} theme={theme}/>
  </div>;
}
