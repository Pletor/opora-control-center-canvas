import type { ReactNode } from "react";
import type { CanvasNode, Job, Project, View, Workspace } from "./types";
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
              <code>{activeWorkspace.directory}</code>
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
