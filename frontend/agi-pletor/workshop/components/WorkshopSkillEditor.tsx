import { useId } from "react";
import type { SkillDoc } from "../logic/workshop-state";
import WorkshopPending from "./WorkshopPending";

type Props = {
  doc: SkillDoc | null; files: string[]; dirty: boolean; pending: boolean; busy: boolean;
  onFile: (path: string) => void; onEdit: (draft: string) => void; onSave: () => void; onDiscard: () => void; onKeep: () => void;
};

/** Okno editoru skillu: výběr souboru skillu, text souboru a Uložit (aktivní jen při změně). */
export default function WorkshopSkillEditor({ doc, files, dirty, pending, busy, onFile, onEdit, onSave, onDiscard, onKeep }: Props) {
  const fileId = useId(), textId = useId();
  if (!doc) return <section className="pletor-workshop__editor" aria-label="Skill"><p className="pletor-workshop__empty">Vyber skill vlevo.</p></section>;
  return (
    <section className="pletor-workshop__editor" aria-label="Skill">
      <header className="pletor-workshop__editor-head">
        <h3 className="pletor-workshop__editor-title">Skill · {doc.name}{dirty && <span className="pletor-workshop__dirty"> ● neuloženo</span>}</h3>
        <label className="pletor-workshop__field-label" htmlFor={fileId}>Soubor</label>
        <select id={fileId} className="pletor-workshop__select" value={doc.path} onChange={(event) => onFile(event.target.value)}>
          {(files.includes(doc.path) ? files : [doc.path, ...files]).map((path) => <option key={path} value={path}>{path}</option>)}
        </select>
        <button type="button" className="pletor-workshop__button pletor-workshop__button--primary" disabled={!dirty || busy} onClick={onSave}>Uložit</button>
      </header>
      {pending && <WorkshopPending onDiscard={onDiscard} onKeep={onKeep} />}
      <label className="pletor-workshop__field-label" htmlFor={textId}>{doc.path}</label>
      <textarea id={textId} className="pletor-workshop__code" value={doc.draft} spellCheck={false} onChange={(event) => onEdit(event.target.value)} />
    </section>
  );
}
