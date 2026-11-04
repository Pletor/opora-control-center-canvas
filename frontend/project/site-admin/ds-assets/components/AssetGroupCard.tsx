import { useState, type DragEvent } from "react";
import type { AssetGroup } from "@/project/site-admin/logic/site-document";
import { fileSize, groupNameProblem, isImage } from "../logic/assets";

/** Jedna skupina assetů: jméno (jen u prázdné), README, mřížka souborů s náhledem obrázků přes `<img>` a drop zóna.
 *  Soubory přetažené sem nebo vybrané tlačítkem hlásí `onUpload`; nahrává a zapisuje rodič. */
export default function AssetGroupCard({ group, groups, url, onUpload, onChange, onRename, onRemove, onRemoveFile }: {
  group: AssetGroup; groups: AssetGroup[]; url: (name: string) => string;
  onUpload: (files: File[]) => void; onChange: (group: AssetGroup) => void; onRename: (name: string) => void;
  onRemove: () => void; onRemoveFile: (name: string) => void;
}) {
  const [name, setName] = useState(group.name);
  const [over, setOver] = useState(false);
  const problem = name === group.name ? "" : groupNameProblem(name, groups, group.name);
  const commit = () => { if (name !== group.name && !problem) onRename(name); else setName(group.name); };
  const drop = (event: DragEvent) => { event.preventDefault(); event.stopPropagation(); setOver(false); onUpload([...event.dataTransfer.files]); };
  return <section className={"ds-assets__group" + (over ? " ds-assets__group--over" : "")} aria-label={"Skupina " + group.name} data-testid={"ds-asset-group-" + group.name}
    onDragOver={(event) => { event.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}>
    <header className="ds-assets__head">
      <input className={"ds-assets__name" + (problem ? " ds-assets__name--problem" : "")} aria-label="Jméno skupiny" value={name} maxLength={64}
        disabled={!!group.files.length} title={group.files.length ? "Skupinu se soubory nejde přejmenovat (soubory mají skupinu v cestě)." : undefined}
        onChange={(event) => setName(event.target.value)} onBlur={commit} onKeyDown={(event) => { if (event.key === "Enter") commit(); }}/>
      <small className="ds-assets__count">{group.files.length} souborů</small>
      <label className="ds-assets__pick">Nahrát soubory
        <input type="file" multiple hidden onChange={(event) => { onUpload([...(event.target.files ?? [])]); event.target.value = ""; }}/>
      </label>
      <button type="button" className="ds-assets__remove" onClick={onRemove}>Odebrat skupinu</button>
    </header>
    {problem && <small className="ds-assets__problem">{problem}</small>}
    {group.files.length ? <ul className="ds-assets__files">
      {group.files.map((file) => <li key={file.name} className="ds-assets__file" data-testid={"ds-asset-" + group.name + "-" + file.name}>
        <a className="ds-assets__thumb" href={url(file.name)} target="_blank" rel="noreferrer">
          {isImage(file) ? <img className="ds-assets__img" src={url(file.name)} alt={file.name} loading="lazy"/>
            : <span className="ds-assets__type">{file.name.split(".").pop()}</span>}
        </a>
        <code className="ds-assets__file-name" title={file.blob}>{file.name}</code>
        <small className="ds-assets__size">{fileSize(file.size)}</small>
        <button type="button" className="ds-assets__file-remove" aria-label={"Odebrat " + file.name} onClick={() => onRemoveFile(file.name)}>×</button>
      </li>)}
    </ul> : <p className="ds-assets__drop">Přetáhni sem soubory (png, jpg, gif, webp, svg, mp4, webm, pdf).</p>}
    <textarea className="ds-assets__readme" aria-label={"README skupiny " + group.name} rows={3} maxLength={64_000} value={group.readme}
      placeholder="Jak assety používat: barva, velikosti, ochranná zóna, kdy které logo." onChange={(event) => onChange({ ...group, readme: event.target.value })}/>
  </section>;
}
