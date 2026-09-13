import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type Project, type View, type Workspace } from "@/types";

/**
 * Jedna kompaktní lišta: projekt, větev, revize a jedno menu s nastavením i operacemi.
 * Každé tlačítko má skutečný handler; git operace se lokálnímu návrhu nenabízejí.
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
  onSelectProject,
  onMain,
  onWorkspace,
  onSelectWorkspace,
  onSurfaceSettings,
  onProjectSettings,
  onRefresh,
  onSync,
  onRemoveProject,
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
  onSelectProject: (id: string) => void;
  onMain: () => void;
  onWorkspace: () => void;
  onSelectWorkspace: (id: string) => void;
  onSurfaceSettings: () => void;
  onProjectSettings: () => void;
  onRefresh: () => void;
  onSync: () => void;
  onRemoveProject: () => void;
  children?: ReactNode;
  projectNavigation?: ReactNode;
  trailing?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const anchor = useRef<HTMLDivElement>(null);
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
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!anchor.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  const item = (label: string, action: () => void, extra?: { danger?: boolean; disabled?: boolean; hint?: string }) => (
    <button
      type="button"
      className={extra?.danger ? "menu-item danger" : "menu-item"}
      disabled={extra?.disabled}
      title={extra?.hint}
      onClick={() => {
        setOpen(false);
        action();
      }}
    >
      {label}
    </button>
  );
  return (
    <header className="topbar" role="banner">
      <div className="brand" title="Opora Control Center">
        <span className="mark" aria-hidden="true">O</span>
        <strong>OPORA</strong>
      </div>
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
      <div className="menu-anchor" ref={anchor}>
        <button
          type="button"
          className="menu-button"
          aria-haspopup="true"
          aria-expanded={open}
          aria-controls="app-menu"
          onClick={() => setOpen((value) => !value)}
        >
          Nastavení
        </button>
        {open && (
          <div id="app-menu" className="menu" role="group" aria-label="Nastavení a operace">
            <div className="menu-head">Tento prohlížeč</div>
            {item("Nastavení plochy", onSurfaceSettings, { hint: "Mřížka a přichytávání; neukládá se do projektu." })}
            <div className="menu-head">Projekt</div>
            {item("Nastavení projektu", onProjectSettings, { hint: "Zadání, LLM návrh a coding v přehledu projektu." })}
            {item("Obnovit pohled", onRefresh, { disabled: busy })}
            {!localProject && item("Synchronizovat main", onSync, { disabled: busy, hint: "Aktualizuje jen čistou spravovanou kopii. Žádný push." })}
            {!localProject && item("Odebrat repozitář", onRemoveProject, { danger: true, disabled: busy, hint: "Odebere ze seznamu; GitHub ani soubory se nemažou." })}
          </div>
        )}
      </div>
      {trailing}
    </header>
  );
}
