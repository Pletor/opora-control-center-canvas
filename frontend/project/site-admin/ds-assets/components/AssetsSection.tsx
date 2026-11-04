import { useState, type DragEvent } from "react";
import type { AssetGroup } from "@/project/site-admin/logic/site-document";
import { fileProblem, newGroupName, renameGroup, withoutFile } from "../logic/assets";
import AssetGroupCard from "./AssetGroupCard";
import "../styles/ds-assets.css";

/** Assets: skupiny souborů (loga, ikony, fotky) s README. „+ New set“ přidá skupinu, soubory jdou přetáhnout na
 *  skupinu nebo kamkoli do sekce (pak do první skupiny, nebo do nové). Soubor, který server nepřijme, dílek řekne
 *  hned a neposílá ho. Skupiny drží rodič, nahrává `onUpload`; odebrání mění jen dokument, ne disk. */
export default function AssetsSection({ groups, uploading, uploadError, assetUrl, onChange, onUpload }: {
  groups: AssetGroup[]; uploading: boolean; uploadError: string; assetUrl: (group: string, name: string) => string;
  onChange: (groups: AssetGroup[]) => void; onUpload: (group: string, files: File[]) => void;
}) {
  const [rejected, setRejected] = useState<string[]>([]);
  const upload = (group: string, files: File[]) => {
    const problems = files.map(fileProblem);
    setRejected(problems.filter(Boolean));
    const fine = files.filter((_file, index) => !problems[index]);
    if (fine.length) onUpload(group, fine);
  };
  const drop = (event: DragEvent) => { event.preventDefault(); upload(groups[0]?.name ?? newGroupName(groups), [...event.dataTransfer.files]); };
  const replace = (name: string, next: AssetGroup) => onChange(groups.map((group) => group.name === name ? next : group));
  return <div className="ds-assets" onDragOver={(event) => event.preventDefault()} onDrop={drop}>
    <div className="ds-assets__bar">
      <button type="button" className="ds-assets__add" onClick={() => onChange([...groups, { name: newGroupName(groups), readme: "", files: [] }])}>+ New set</button>
      <small className="ds-assets__hint">Přetáhni soubory kamkoli sem. Odebraný soubor zůstane na disku projektu, z dokumentu zmizí po Uložit.</small>
      {uploading && <span className="ds-assets__status" role="status">Nahrávám…</span>}
    </div>
    {(uploadError || rejected.length > 0) && <ul className="ds-assets__errors" role="alert">
      {uploadError && <li>{uploadError}</li>}
      {rejected.map((problem) => <li key={problem}>{problem}</li>)}
    </ul>}
    {!groups.length && <p className="ds-assets__empty">Zatím žádné soubory. Přidej skupinu nebo sem přetáhni loga a ikony.</p>}
    {groups.map((group) => <AssetGroupCard key={group.name} group={group} groups={groups} url={(name) => assetUrl(group.name, name)}
      onUpload={(files) => upload(group.name, files)} onChange={(next) => replace(group.name, next)}
      onRename={(name) => onChange(renameGroup(groups, group.name, name))}
      onRemove={() => { if (!group.files.length || window.confirm(`Odebrat skupinu ${group.name} z design systému? Soubory zůstanou na disku.`)) onChange(groups.filter((one) => one.name !== group.name)); }}
      onRemoveFile={(name) => onChange(withoutFile(groups, group.name, name))}/>)}
  </div>;
}
