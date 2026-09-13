import { useState } from "react";
import { SOURCE_DRAG_TYPE, type WorkspaceSelection } from "@/shared/selection/logic/workspace-selection";

export default function ContextShelf({ project, workspace, value, onChange, onAdd, onOpen }: {
  project: string; workspace: string; value: WorkspaceSelection; onChange: (update: Partial<WorkspaceSelection>) => void;
  onAdd: (path: string) => boolean; onOpen: (path: string) => void;
}) {
  const [message, setMessage] = useState("");
  return <aside className="context-shelf" aria-label="Kontext Editoru" onDragOver={(e) => {
    if (e.dataTransfer.types.includes(SOURCE_DRAG_TYPE)) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; }
  }} onDrop={(e) => {
    e.preventDefault();
    try {
      const ref = JSON.parse(e.dataTransfer.getData(SOURCE_DRAG_TYPE));
      if (ref.project !== project || ref.workspace !== workspace || typeof ref.path !== "string" || !onAdd(ref.path)) throw new Error();
      setMessage("Reference přidána; obsah souboru nebyl načten.");
    } catch { setMessage("Reference nepatří do tohoto prostoru nebo není povolená."); }
  }}>
    <div className="eyebrow">SPOLEČNÝ PRACOVNÍ KONTEXT</div><h2>Kontext Editoru</h2>
    <p className="muted">Cesty ze stromu přidejte tlačítkem nebo přetažením. Jde o reference, ne automatické čtení souborů.</p>
    <ul className="context-references">{value.references.map((path) => <li key={path}>
      <button className="reference-path" title="Otevřít dokumentaci zdroje" onClick={() => onOpen(path)}>{path}</button>
      <button aria-label={"Odebrat z kontextu " + path} onClick={() => onChange({ references: value.references.filter((item) => item !== path) })}>×</button>
    </li>)}</ul>
    {!value.references.length && <p className="muted">Zatím bez cest. Bloky, deníky a kresby zůstávají součástí Editoru.</p>}
    <label className="field">Poznámka ke kontextu<textarea aria-label="Poznámka ke kontextu" rows={6} maxLength={16000}
      value={value.note} onChange={(e) => onChange({ note: e.target.value })} /></label>
    <small className="muted">{value.references.length}/100 referencí · citlivé a generované cesty se nepřidávají. Nic se samo neodesílá modelu.</small>
    {message && <p role="status">{message}</p>}
  </aside>;
}
