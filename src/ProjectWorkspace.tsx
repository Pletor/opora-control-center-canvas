import { useState, type ReactNode } from "react";
import ContextShelf from "./ContextShelf";
import SourceExplorer from "./SourceExplorer";
import WorkspaceDocumentEditor from "./WorkspaceDocumentEditor";
import { allowedReference, type WorkspaceSelection } from "./workspace-selection";

/** memory = napojený ProjectMemoryPanel (Sonnet); bez něj se karta Paměť projektu nenabízí. */
export default function ProjectWorkspace({ project, workspace, selection, onChange, onAdd, onSettings, memory = null }: {
  project: string; workspace: string; selection: WorkspaceSelection; onChange: (update: Partial<WorkspaceSelection>) => void;
  onAdd: (path: string) => boolean; onSettings: () => void; memory?: ReactNode;
}) {
  const [search, setSearch] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [message, setMessage] = useState("");
  const [view, setView] = useState<"document" | "memory">("document");
  const showMemory = !!memory && view === "memory";
  return <section className="project-workspace" aria-label="Projekt">
    <div role="toolbar" aria-label="Nástroje Projektu" className="environment-toolbar v3-toolbar">
      <div className="v3-tool-group" role="group" aria-label="Strom">
        <span className="v3-tool-label">Strom</span>
        <input aria-label="Hledat v načteném stromu" placeholder="Hledat v načteném stromu…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <button onClick={() => setRefresh((value) => value + 1)}>Obnovit strom</button>
      </div>
      <div className="v3-tool-group" role="group" aria-label="Dokumentace">
        <span className="v3-tool-label">Dokumentace</span>
        <button className="primary" disabled={!allowedReference(selection.sourcePath)} onClick={() => setMessage(onAdd(selection.sourcePath) ? "Reference je v kontextu Editoru." : "Kontext nepřijímá tuto cestu (limit nebo citlivý zdroj).")}>Přidat do kontextu</button>
        {memory && <>
          <button aria-pressed={view === "document"} onClick={() => setView("document")}>Cesta</button>
          <button aria-pressed={view === "memory"} onClick={() => setView("memory")}>Paměť projektu</button>
        </>}
      </div>
      <span className="v3-grow" />
      <button className="v3-quiet" onClick={onSettings}>Připojení a nastavení projektu</button>
      {message && <span role="status">{message}</span>}
    </div>
    <div className="project-columns">
      <SourceExplorer key={JSON.stringify([project, workspace])} project={project} workspace={workspace} selected={selection.sourcePath}
        onSelect={(path) => onChange({ sourcePath: path })} search={search} refresh={refresh} />
      <div className="document-area">
        {showMemory ? <div className="v3-slot v3-project-memory">{memory}</div>
          : <WorkspaceDocumentEditor key={JSON.stringify([project, workspace, selection.sourcePath])} project={project} workspace={workspace} path={selection.sourcePath} />}
      </div>
      <ContextShelf project={project} workspace={workspace} value={selection} onChange={onChange} onAdd={onAdd} onOpen={(path) => { setView("document"); onChange({ sourcePath: path }); }} />
    </div>
  </section>;
}
