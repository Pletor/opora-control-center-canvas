import { useState } from "react";
import ContextShelf from "./ContextShelf";
import SourceExplorer from "./SourceExplorer";
import WorkspaceDocumentEditor from "./WorkspaceDocumentEditor";
import { allowedReference, type WorkspaceSelection } from "./workspace-selection";

export default function ProjectWorkspace({ project, workspace, selection, onChange, onAdd, onSettings }: {
  project: string; workspace: string; selection: WorkspaceSelection; onChange: (update: Partial<WorkspaceSelection>) => void;
  onAdd: (path: string) => boolean; onSettings: () => void;
}) {
  const [search, setSearch] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [message, setMessage] = useState("");
  return <section className="project-workspace" aria-label="Projekt">
    <div role="toolbar" aria-label="Nástroje Projektu" className="environment-toolbar">
      <strong>Projekt</strong><input aria-label="Hledat v načteném stromu" placeholder="Hledat v načteném stromu…" value={search} onChange={(e) => setSearch(e.target.value)} />
      <button onClick={() => setRefresh((value) => value + 1)}>Obnovit strom</button>
      <button disabled={!allowedReference(selection.sourcePath)} onClick={() => setMessage(onAdd(selection.sourcePath) ? "Reference je v kontextu Editoru." : "Kontext nepřijímá tuto cestu (limit nebo citlivý zdroj).")}>Přidat do kontextu</button>
      <button onClick={onSettings}>Připojení a nastavení projektu</button>
      {message && <span role="status">{message}</span>}
    </div>
    <div className="project-columns">
      <SourceExplorer key={JSON.stringify([project, workspace])} project={project} workspace={workspace} selected={selection.sourcePath}
        onSelect={(path) => onChange({ sourcePath: path })} search={search} refresh={refresh} />
      <div className="document-area"><WorkspaceDocumentEditor key={JSON.stringify([project, workspace, selection.sourcePath])} project={project} workspace={workspace} path={selection.sourcePath} /></div>
      <ContextShelf project={project} workspace={workspace} value={selection} onChange={onChange} onAdd={onAdd} onOpen={(path) => onChange({ sourcePath: path })} />
    </div>
  </section>;
}
