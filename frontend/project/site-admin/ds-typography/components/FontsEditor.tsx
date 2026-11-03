import type { FontFile } from "@/project/site-admin/logic/site-document";
import { FONT_ACCEPT } from "../logic/typography";

/** Fonty projektu: záznamy `type.fonts` (rodina, váha, řez, soubor) a nahrání souboru. Nahrání vyřizuje rodič
 *  (`POST /api/site-admin/fonts`), dílek jen hlásí vybraný soubor a ukazuje stav. */
export default function FontsEditor({ fonts, uploading, error, onUpload, onChange, onRemove }: {
  fonts: FontFile[]; uploading: boolean; error: string;
  onUpload: (file: File) => void; onChange: (index: number, font: FontFile) => void; onRemove: (index: number) => void;
}) {
  return <div className="ds-type__block">
    <h4 className="ds-type__title">Fonty</h4>
    {!fonts.length && <p className="ds-type__empty">Zatím žádné vlastní fonty. Nahraj woff2, woff, ttf nebo otf; systémová a hostovaná písma stačí zapsat do rodiny.</p>}
    {fonts.map((font, index) => <div key={font.file + index} className="ds-type__font">
      <span className="ds-type__font-sample" style={{ fontFamily: `"${font.family}"`, fontWeight: String(font.weight).split(" ")[0], fontStyle: font.style }}>Aa</span>
      <input className="ds-type__input" aria-label="Rodina fontu" value={font.family} maxLength={64} onChange={(event) => onChange(index, { ...font, family: event.target.value })}/>
      <input className="ds-type__input ds-type__input--short" aria-label="Váha fontu" value={String(font.weight)} maxLength={9} placeholder="400 nebo 300 800" onChange={(event) => onChange(index, { ...font, weight: event.target.value })}/>
      <select className="ds-type__input" aria-label="Řez fontu" value={font.style} onChange={(event) => onChange(index, { ...font, style: event.target.value })}>
        <option value="normal">normal</option><option value="italic">italic</option><option value="oblique">oblique</option>
      </select>
      <code className="ds-type__var">{font.file}</code>
      <button type="button" className="ds-type__remove" aria-label={"Odebrat font " + font.file} onClick={() => onRemove(index)}>×</button>
    </div>)}
    <label className={"ds-type__add ds-type__upload" + (uploading ? " ds-type__upload--busy" : "")}>
      {uploading ? "Nahrávám…" : "⤒ Nahrát font"}
      <input type="file" className="ds-type__file" accept={FONT_ACCEPT} disabled={uploading} data-testid="font-upload"
        onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) onUpload(file); }}/>
    </label>
    {error && <p className="ds-type__error" role="alert">{error}</p>}
  </div>;
}
