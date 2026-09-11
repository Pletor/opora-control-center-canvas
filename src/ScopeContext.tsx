import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type CanvasNode, type Job, type Project, type View, type Workspace } from "./types";
import { WORKSPACE_MODES, type WorkspaceMode } from "./workspace-settings";

/**
 * Inspektor bez výběru: skutečný kontext pohledu (zdroj, worktree, operace)
 * a nástroje aktuálního módu. Žádné dekorace, žádné vymyšlené metriky.
 */
export default function ScopeContext({
  mode,
  layer,
  activeProject,
  view,
  activeWorkspace,
  jobs,
  localProject,
  tools,
  onWorkspace,
}: {
  mode: WorkspaceMode;
  layer?: CanvasNode;
  activeProject?: Project;
  view: View | null;
  activeWorkspace?: Workspace;
  jobs: Job[];
  localProject: boolean;
  /** Nástroje módu (mapa, kreslení) patří před obecný kontext. */
  tools?: ReactNode;
  onWorkspace: () => void;
}) {
  const modeInfo = WORKSPACE_MODES.find((m) => m.key === mode);
  const [opening, setOpening] = useState(false);
  const [openResult, setOpenResult] = useState<{ error: boolean; text: string } | null>(null);
  const openingLock = useRef(false);
  const generation = useRef(0);
  useEffect(() => {
    generation.current++; setOpenResult(null);
    return () => { generation.current++; };
  }, [activeProject?.id, activeWorkspace?.id]);
  async function openWorktree() {
    if (!activeProject || !activeWorkspace || openingLock.current) return;
    openingLock.current = true; setOpening(true); setOpenResult(null);
    const ticket = generation.current;
    try {
      const result = await api<{ project: string; workspace: string; path: string; action: string; status: string }>("/api/workspace/open-file", {
        project: activeProject.id, workspace: activeWorkspace.id, path: "", action: "workspace-vscode",
      });
      if (ticket !== generation.current) return;
      if (result.project !== activeProject.id || result.workspace !== activeWorkspace.id || result.path !== "" || result.action !== "workspace-vscode" || result.status !== "requested") throw new Error("Odpověď neodpovídá vybranému worktree.");
      setOpenResult({ error: false, text: "Požadavek na nové okno VS Code předán systému." });
    } catch (error) {
      if (ticket === generation.current) setOpenResult({ error: true, text: String(error) });
    } finally { openingLock.current = false; setOpening(false); }
  }
  const hint =
    mode === "structure"
      ? "Vyberte kartu na plátně. Dvojklik na prázdné místo vytvoří uzel."
      : mode === "text"
        ? "Otevřete vrstvu, aby měl dokument svůj deník a souvislosti."
        : mode === "map"
          ? "Klik vybere uzel nebo vazbu, dvojklik otevře vrstvu ve Struktuře."
          : modeInfo?.hint ?? "";
  return (
    <div className="scope-context" data-testid="scope-context">
      <div className="eyebrow">{(modeInfo?.label ?? "").toLocaleUpperCase("cs")} · KONTEXT</div>
      <h2>{layer?.name ?? activeProject?.name ?? "Lokální návrh"}</h2>
      {hint && <p className="muted">{hint}</p>}
      {tools}
      <dl className="facts">
        <dt>Zdroj</dt>
        <dd>{view?.source ?? "Načítám pouze vybraný pohled…"}</dd>
        {view && (
          <>
            <dt>Pozorováno</dt>
            <dd>{new Date(view.observedAt).toLocaleTimeString("cs-CZ")}</dd>
          </>
        )}
        {activeWorkspace && (
          <>
            <dt>Worktree</dt>
            <dd>
              <div className="worktree-open-row"><code>{activeWorkspace.directory}</code>
                <button type="button" className="worktree-open-button" disabled={opening || !activeProject}
                  aria-label="Otevřít worktree v novém okně VS Code" title="Otevřít tento pracovní prostor v novém okně VS Code" onClick={() => void openWorktree()}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M14 3h7v7M21 3 10 14M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5" /></svg>
                </button>
              </div>
              {openResult && <span role={openResult.error ? "alert" : "status"} className={openResult.error ? "error" : "muted"}>{openResult.text}</span>}
              <span className="muted">Vlastník {activeWorkspace.actor}. Tím není potvrzena aktivita agenta.</span>
            </dd>
          </>
        )}
      </dl>
      <h3>Operace</h3>
      {jobs.length ? (
        <ul className="job-list">
          {jobs.slice(0, 4).map((j) => (
            <li key={j.id}>
              <strong>
                {j.kind} · {j.status}
              </strong>
              <span>{j.message}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Žádná spuštěná Git operace.</p>
      )}
      {!localProject && (
        <button type="button" onClick={onWorkspace}>
          Nový pracovní prostor
        </button>
      )}
      <p className="boundary-note">Merge se řídí pravidly repozitáře. Plátno samo nepovoluje push ani spuštění agenta.</p>
    </div>
  );
}
