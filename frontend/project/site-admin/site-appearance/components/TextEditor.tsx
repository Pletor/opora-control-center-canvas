import { ColorField, Field, TextField } from "@/project/site-admin/site-fields/components/Fields";
import type { Appearance, Leaf } from "../logic/appearance";

const text = (value: Leaf) => value === null ? "" : String(value);

/** Písmo nadpisů, podnadpisů a textů s velikostí a barvy textu a odkazů. Písmo je stack (`"Inter", sans-serif`);
 *  nabídka ukazuje rodiny, které systém už má v Typography. */
export default function TextEditor({ appearance, aliases, stacks, onField }: {
  appearance: Appearance; aliases: string[]; stacks: string[]; onField: (path: string, value: Leaf) => void;
}) {
  const { text: fonts, colors } = appearance;
  const font = (label: string, path: string, value: Leaf) => <Field label={label}>
    <input className="site-fields__input" value={text(value)} list="site-appearance-stacks" placeholder="zdědí písmo webu" maxLength={200}
      spellCheck={false} onChange={(event) => onField(path, event.target.value)}/>
  </Field>;
  return <>
    <fieldset className="site-appearance__group">
      <legend className="site-appearance__legend">Písmo</legend>
      <datalist id="site-appearance-stacks">{stacks.map((stack) => <option key={stack} value={stack}/>)}</datalist>
      <div className="site-appearance__grid">
        {font("Font nadpisů", "text.heading.font", fonts.heading.font)}
        {font("Font podnadpisů", "text.subheading.font", fonts.subheading.font)}
        {font("Font textů", "text.body.font", fonts.body.font)}
        <span className="site-appearance__spacer" aria-hidden="true"/>
        <TextField label="Velikost podnadpisů" value={text(fonts.subheading.size)} placeholder="1.25rem" onChange={(value) => onField("text.subheading.size", value)}/>
        <TextField label="Velikost textů" value={text(fonts.body.size)} placeholder="1rem" onChange={(value) => onField("text.body.size", value)}/>
      </div>
    </fieldset>
    <fieldset className="site-appearance__group">
      <legend className="site-appearance__legend">Barvy textu</legend>
      <div className="site-appearance__grid">
        <ColorField label="Barva textu" value={text(colors.text)} placeholder="token ink" aliases={aliases} onChange={(value) => onField("colors.text", value)}/>
        <ColorField label="Barva inverzních textů" value={text(colors.textInverse)} placeholder="token ink-inverse" aliases={aliases} onChange={(value) => onField("colors.textInverse", value)}/>
        <ColorField label="Barva odkazů" value={text(colors.link)} placeholder="token link" aliases={aliases} onChange={(value) => onField("colors.link", value)}/>
        <ColorField label="Odkaz po najetí" value={text(colors.linkHover)} placeholder="token link-hover" aliases={aliases} onChange={(value) => onField("colors.linkHover", value)}/>
        <ColorField label="Focus (obrys při ovládání klávesnicí)" value={text(colors.focus)} placeholder="token focus" aliases={aliases} onChange={(value) => onField("colors.focus", value)}/>
      </div>
    </fieldset>
  </>;
}
