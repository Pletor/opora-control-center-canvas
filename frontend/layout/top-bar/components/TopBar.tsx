import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type Project, type View, type Workspace } from "@/shared/types/logic/types";

/**
 * Jedna kompaktní lišta: projekt, větev, revize a přepínač prostředí.
 * Nastavení i operace projektu žijí v Nastavení (levý dolní roh), ne tady.
 */
export default function TopBar({
  projects,
  draftProject,
  project,
  busy,
  localProject,
  workspace,
  view,
  activeWorkspace,
  onHome,
  onSelectProject,
  onMain,
  onWorkspace,
  onSelectWorkspace,
  children,
  projectNavigation,
  trailing,
}: {
  projects: Project[];
  draftProject?: Project;
  project: string;
  busy: boolean;
  localProject: boolean;
  workspace: string;
  view: View | null;
  activeWorkspace?: Workspace;
  onHome: () => void;
  onSelectProject: (id: string) => void;
  onMain: () => void;
  onWorkspace: () => void;
  onSelectWorkspace: (id: string) => void;
  children?: ReactNode;
  projectNavigation?: ReactNode;
  /** Slot úplně vpravo, za nápisem LOKÁLNĚ (tlačítko Asistent). */
  trailing?: ReactNode;
}) {
  const [openingWorktree, setOpeningWorktree] = useState(false);
  const [worktreeResult, setWorktreeResult] = useState<{ error: boolean; text: string } | null>(null);
  const worktreeLock = useRef(false);
  const worktreeGeneration = useRef(0);
  useEffect(() => {
    worktreeGeneration.current++; setWorktreeResult(null);
    return () => { worktreeGeneration.current++; };
  }, [project, workspace]);
  async function openSelectedWorktree() {
    if (busy || worktreeLock.current || !activeWorkspace || activeWorkspace.id !== workspace) return;
    worktreeLock.current = true; setOpeningWorktree(true); setWorktreeResult(null);
    const ticket = worktreeGeneration.current;
    try {
      const result = await api<{ project: string; workspace: string; path: string; action: string; status: string }>("/api/workspace/open-file", {
        project, workspace, path: "", action: "workspace-vscode",
      });
      if (ticket !== worktreeGeneration.current) return;
      if (result.project !== project || result.workspace !== workspace || result.path !== "" || result.action !== "workspace-vscode" || result.status !== "requested") throw new Error("Odpověď neodpovídá vybranému worktree.");
      setWorktreeResult({ error: false, text: "Požadavek na nové okno VS Code předán systému." });
    } catch (error) {
      if (ticket === worktreeGeneration.current) setWorktreeResult({ error: true, text: String(error) });
    } finally { worktreeLock.current = false; setOpeningWorktree(false); }
  }
  return (
    <header className="topbar" role="banner">
      <button type="button" className="brand" title="Přehled repozitářů" aria-label="Opora — přehled repozitářů" data-testid="opora-home" disabled={busy} onClick={onHome}>
        <span className="mark" aria-hidden="true">O</span>
        <strong>OPORA</strong>
      </button>
      <label className="topbar-field">
        <span>Projekt</span>
        <select aria-label="Projekt" disabled={busy} value={project} onChange={(e) => onSelectProject(e.target.value)}>
          <option value="draft">{draftProject?.name ?? "Lokální návrh"} · bez repozitáře</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      {projectNavigation}
      {!localProject && (
        <div className="segment" role="group" aria-label="Pracovní větev">
          <button type="button" aria-pressed={workspace === "main"} disabled={busy} onClick={onMain}>
            Čistý main
          </button>
          <button type="button" aria-pressed={workspace !== "main"} disabled={busy} onClick={onWorkspace}>
            Pracovní prostor
          </button>
        </div>
      )}
      {activeWorkspace && (
        <div className="topbar-worktree" role="group" aria-label="Vybraný pracovní strom">
        <select
          aria-label="Pracovní strom"
          className="topbar-select"
          value={workspace}
          disabled={busy}
          onChange={(e) => onSelectWorkspace(e.target.value)}
        >
          {view?.workspaces.map((w) => (
            <option key={w.id} value={w.id}>
              {w.actor} · {w.node_id}
            </option>
          ))}
        </select>
        <button type="button" className="worktree-open-button"
          disabled={busy || openingWorktree || activeWorkspace.id !== workspace}
          aria-label="Otevřít vybraný worktree v novém okně VS Code"
          title="Otevřít vybraný worktree v novém okně VS Code" onClick={() => void openSelectedWorktree()}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M14 3h7v7M21 3 10 14M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5" /></svg>
        </button>
        {worktreeResult && <span className={"topbar-worktree-result " + (worktreeResult.error ? "error" : "muted")} role={worktreeResult.error ? "alert" : "status"}>{worktreeResult.text}</span>}
        </div>
      )}
      {children}
      <div className="topbar-spacer" />
      {!localProject && (
        <div className="revision" title="Sledovaná větev a revize spravované kopie">
          <code>
            {view?.branch ?? "načítání"} · {view?.sha?.slice(0, 12)}
          </code>
          {view?.dirty && <span className="warn-text">Pracovní soubory změněny</span>}
        </div>
      )}
      <span className="local-status">LOKÁLNĚ · {location.port}</span>
      {trailing}
    </header>
  );
}
