import type { TypeFamily } from "@/project/site-admin/logic/site-document";
import { addFamily, addGroup, addStyle, MAX_GROUPS, MAX_STYLES, removeFamily, removeFont, removeGroup, setFamily, totalStyles, updateFont, updateGroup } from "../logic/typography";
import FamiliesEditor from "./FamiliesEditor";
import FontsEditor from "./FontsEditor";
import TypeGroupEditor from "./TypeGroupEditor";
import "../styles/ds-typography.css";

/** Typography: rodiny, fonty a skupiny stylů s živou ukázkou. Dílek dostane `type` a každou změnu hlásí celým `type`;
 *  nahrání fontu (zápis souboru na server) a přidání jeho záznamu vyřizuje rodič přes `onUploadFont`. */
export default function TypographySection({ type, theme, uploading, uploadError, onChange, onUploadFont }: {
  type: TypeFamily; theme: string; uploading: boolean; uploadError: string;
  onChange: (type: TypeFamily) => void; onUploadFont: (file: File) => void;
}) {
  const families = Object.keys(type.families);
  const canAddStyle = totalStyles(type) < MAX_STYLES;
  return <div className="ds-type">
    <div className="ds-type__columns">
      <FamiliesEditor families={type.families} onChange={(key, next, stack) => onChange(setFamily(type, key, next, stack))}
        onAdd={(key) => onChange(addFamily(type, key, "system-ui, sans-serif"))} onRemove={(key) => onChange(removeFamily(type, key))}/>
      <FontsEditor fonts={type.fonts} uploading={uploading} error={uploadError} onUpload={onUploadFont}
        onChange={(index, font) => onChange(updateFont(type, index, font))} onRemove={(index) => onChange(removeFont(type, index))}/>
    </div>
    <h4 className="ds-type__title">Styly</h4>
    {!type.groups.length && <p className="ds-type__empty">Zatím žádné styly. Skupina „Text“ s kroky display, heading, body a caption pokryje většinu webu.</p>}
    {type.groups.map((group, index) => <TypeGroupEditor key={index} group={group} families={families} theme={theme} canAddStyle={canAddStyle}
      onChange={(next) => onChange(updateGroup(type, index, next))} onAddStyle={() => onChange(addStyle(type, index))} onRemove={() => onChange(removeGroup(type, index))}/>)}
    <button type="button" className="ds-type__add" disabled={type.groups.length >= MAX_GROUPS} onClick={() => onChange(addGroup(type, type.groups.length ? `Skupina ${type.groups.length + 1}` : "Text"))}>+ Skupina stylů</button>
  </div>;
}
