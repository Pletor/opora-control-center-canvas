import { useEffect, useRef, useState, lazy, Suspense } from "react";
import Board from "./Board";
import ProjectHome from "./ProjectHome";
import TextWorkspace from "./TextWorkspace";
import { AgentTaskNotice, emitAgentTask, type AgentTaskRequest } from "./context-actions";
import PlanPanel from "./PlanPanel";
import CodingPanel from "./CodingPanel";
import type { WireframeKind } from "./wireframe-model";
import DrawingTools from "./DrawingTools";
import { discardDrawingDrafts, type DrawingTool } from "./drawing-state";
const DrawingWorkspace = lazy(() => import("./DrawingWorkspace"));
import ProjectMap from "./ProjectMap";
import WorkspaceSettings from "./WorkspaceSettings";
import WorkspaceBoundary from "./WorkspaceBoundary";
import {
  readMode,
  readSettings,
  SETTINGS_KEY,
  type WorkspaceMode,
  type SurfaceSettings,
} from "./workspace-settings";
import { downloadArchify } from "./project-map";
import "./workspace-modes.css";
import NodePanel from "./NodePanel";
import RemovalDialog from "./RemovalDialog";
import { discardSpecDrafts } from "./NodeSpecEditor";
import {
  api,
  type Graph,
  type View,
  type Project,
  type Job,
  type CanvasNode,
  type Workspace,
  type RemovalPreview,
} from "./types";
const initial = new URLSearchParams(location.search);
export default function App() {
  const [screen, setScreen] = useState<"home" | "canvas">(() => initial.get("screen") === "home" ? "home" : initial.get("screen") === "canvas" || initial.has("mode") || initial.has("layer") || initial.has("workspace") ? "canvas" : "home");
  const [draftProject, setDraftProject] = useState<Project | undefined>();
  const [wireframeMode, setWireframeMode] = useState(initial.get("wireframe") === "1");
  const [wireframeInsert, setWireframeInsert] = useState<{ kind: WireframeKind; sequence: number }>();
  const lastLoadedScope = useRef("");
  const [project, setProject] = useState(initial.get("project") ?? "draft");
  const [workspace, setWorkspace] = useState(
    initial.get("workspace") ?? "draft",
  );
  const [drawingTool, setDrawingTool] = useState<DrawingTool>("selection");
  const [drawingCommand, setDrawingCommand] = useState<{
    type: DrawingTool;
    sequence: number;
  }>({ type: "selection", sequence: 0 });
  const [drawingReady, setDrawingReady] = useState(false);
  const [mode, setMode] = useState<WorkspaceMode>(() =>
    readMode(initial.get("mode")),
  );
  const [editingName, setEditingName] = useState<string | null>(null);
  const [agentTask, setAgentTask] = useState<AgentTaskRequest | null>(null);
  const [settings, setSettings] = useState(readSettings);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [linkSource, setLinkSource] = useState("");
  const [linkTarget, setLinkTarget] = useState("");
  const [parent, setParent] = useState<string | null>(initial.get("layer"));
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [removal, setRemoval] = useState<RemovalPreview | null>(null);
  const activeScope = useRef({ project, workspace });
  activeScope.current = { project, workspace };
  const activeContext = useRef("");
  activeContext.current = JSON.stringify([
    project,
    workspace,
    parent,
    selected,
    selectedEdge,
  ]);
  const bootstrapGeneration = useRef(0);
  const [projects, setProjects] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [view, setView] = useState<View | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [modal, setModal] = useState<
    "github" | "sector" | "node" | "workspace" | null
  >(null);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [approved, setApproved] = useState(false);
  const [actor, setActor] = useState("");
  const generation = useRef(0);
  async function bootstrap() {
    const ticket = ++bootstrapGeneration.current;
    const b = await api<{ projects: Project[]; jobs: Job[]; draft?: Project }>("/api/bootstrap");
    if (ticket !== bootstrapGeneration.current) return;
    setProjects(b.projects);
    setDraftProject(b.draft);
    setJobs(b.jobs);
  }
  async function refresh() {
    const g = ++generation.current;
    setView(null);
    try {
      const v = await api<View>(
        `/api/view?project=${encodeURIComponent(project)}&workspace=${encodeURIComponent(workspace)}`,
      );
      if (g === generation.current) setView(v);
    } catch (e) {
      if (g === generation.current) setError(String(e));
    }
  }
  useEffect(() => {
    bootstrap().catch((e) => setError(String(e)));
    const t = setInterval(() => bootstrap().catch(() => {}), 2500);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    const nextScope = JSON.stringify([project, workspace]);
    if (lastLoadedScope.current !== nextScope) {
      setSelected(null); setSelectedEdge(null); setRemoval(null); lastLoadedScope.current = nextScope;
    }
    setError("");
    if (screen === "canvas") refresh(); else generation.current++;
  }, [project, workspace, screen]);
  useEffect(() => {
    const q = new URLSearchParams({ project, workspace, mode, screen });
    if (parent) q.set("layer", parent);
    if (wireframeMode) q.set("wireframe", "1");
    history.replaceState(null, "", "/?" + q);
  }, [project, workspace, parent, mode, screen, wireframeMode]);
  const completed = jobs
    .filter((j) => j.status === "complete" && j.project_id === project)
    .map((j) => j.id)
    .join(",");
  useEffect(() => {
    if (completed && screen === "canvas") refresh();
  }, [completed]);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function save(graph: Graph) {
    if (!view) return;
    setView(
      await api<View>("/api/graph", {
        project,
        workspace,
        graph,
        digest: view.digest,
      }),
    );
  }
  const graph = view?.graph ?? { nodes: [], edges: [] };
  const node = graph.nodes.find((n) => n.id === selected);
  const edge = graph.edges.find((e) => e.id === selectedEdge);
  const layer = graph.nodes.find((n) => n.id === parent);
  const editable = !!view && !view.readOnly && !busy;
  const visible = graph.nodes.filter((n) => n.parentId === parent);
  const visibleIds = new Set(visible.map((n) => n.id));
  const outsideLinks = graph.edges.filter(
    (e) =>
      (visibleIds.has(e.source) || visibleIds.has(e.target)) &&
      !(visibleIds.has(e.source) && visibleIds.has(e.target)),
  ).length;
  const ancestors: CanvasNode[] = [];
  let cursor = layer;
  while (cursor) {
    ancestors.unshift(cursor);
    cursor = graph.nodes.find((n) => n.id === cursor!.parentId);
  }
  const activeWorkspace = view?.workspaces.find((w) => w.id === workspace);
  const activeProject = project === "draft" ? draftProject : projects.find((p) => p.id === project);
  const localProject = project === "draft" || ["local", "empty", "builtin"].includes(activeProject?.sourceKind ?? "");
  const linkTargets = graph.nodes.map((n) => ({ id: n.id, name: n.name, kind: n.kind }));
  /** Odkaz i souvislost vedou na tentýž uzel: otevře se jeho vrstva a označí se. */
  function openNode(id: string) {
    const target = graph.nodes.find((n) => n.id === id);
    if (!target) return;
    setParent(target.parentId);
    setSelected(target.id);
    setSelectedEdge(null);
  }
  /** Kontextová akce: rodičovská integrace dostane přesný scope, běh nevzniká zde. */
  function requestAgentTask(nodeId: string, text: string, source: AgentTaskRequest["source"]) {
    const target = graph.nodes.find((n) => n.id === nodeId);
    setAgentTask(
      emitAgentTask({
        project,
        workspace,
        layer: parent,
        nodeId,
        nodeName: target?.name ?? nodeId,
        source,
        text,
        requestedAt: new Date().toISOString(),
      }),
    );
  }
  function open(kind: typeof modal) {
    setModal(kind);
    setName("");
    setApproved(false);
  }
  function enter(id: string | null) {
    setParent(id);
    setSelected(null);
    setSelectedEdge(null);
  }
  function selectProject(id: string, sourceKind?: string) {
    generation.current++;
    setView(null);
    setProject(id);
    const kind = sourceKind ?? projects.find((p) => p.id === id)?.sourceKind;
    setWorkspace(id === "draft" || ["local", "empty", "builtin"].includes(kind ?? "") ? "draft" : "main");
    enter(null);
  }
  function updateSettings(value: SurfaceSettings) {
    setSettings(value);
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(value));
    } catch {
      setError("Nastavení nyní platí, ale prohlížeč je nemohl uložit.");
    }
  }
  function connectGraph(source: string, target: string) {
    if (!editable || source === target) return;
    if (graph.edges.some((e) => e.source === source && e.target === target)) {
      setError("Toto propojení už existuje.");
      return;
    }
    run(() =>
      save({
        ...graph,
        edges: [...graph.edges, { id: crypto.randomUUID(), source, target }],
      }),
    );
  }
  async function requestRemoval(kind: RemovalPreview["kind"], target: string) {
    const context = activeContext.current;
    await run(async () => {
      const preview = await api<RemovalPreview>(
        "/api/removal-preview?" +
          new URLSearchParams({
            project,
            workspace: kind === "project" ? "main" : workspace,
            kind,
            target,
          }),
      );
      if (context === activeContext.current) setRemoval(preview);
    });
  }
  async function confirmRemoval(preview: RemovalPreview) {
    const result = await api<{
      view?: View;
      nodeIds?: string[];
      removedProject?: string;
    }>("/api/remove", {
      project: preview.project,
      workspace: preview.workspace,
      kind: preview.kind,
      target: preview.target,
      digest: preview.digest,
      confirmed: true,
    });
    generation.current++;
    if (preview.kind === "project") {
      bootstrapGeneration.current++;
      discardSpecDrafts(preview.project);
      discardDrawingDrafts(preview.project);
      setProjects((items) => items.filter((p) => p.id !== preview.project));
      setJobs((items) => items.filter((j) => j.project_id !== preview.project));
      if (activeScope.current.project === preview.project)
        selectProject("draft");
      bootstrap().catch((e) => setError(String(e)));
    } else {
      discardSpecDrafts(
        preview.project,
        preview.workspace,
        result.nodeIds ?? [],
      );
      discardDrawingDrafts(
        preview.project,
        preview.workspace,
        result.nodeIds ?? [],
      );
      if (
        activeScope.current.project === preview.project &&
        activeScope.current.workspace === preview.workspace &&
        result.view
      ) {
        setView(result.view);
        setSelected(null);
        setSelectedEdge(null);
        if (parent && result.nodeIds?.includes(parent)) setParent(null);
      }
    }
    setRemoval((current) =>
      current?.digest === preview.digest ? null : current,
    );
  }
  if (screen === "home") return <>
    <ProjectHome projects={projects} draftProject={draftProject} projectId={project} jobs={jobs} onChoose={selectProject} onRefresh={bootstrap} onOpen={() => setScreen("canvas")} onRemove={() => requestRemoval("project", project)} renderLLM={(_snapshot, dirty) => <><PlanPanel key={project + ":plan"} project={project} dirty={dirty} /><CodingPanel key={project + ":coding"} project={project} dirty={dirty} /></>} />
    {removal && <RemovalDialog key={removal.digest} preview={removal} onClose={() => setRemoval(null)} onConfirm={confirmRemoval} />}
  </>;
  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="symbol">O</span>
          <strong>
            OPORA<span>CONTROL CENTER</span>
          </strong>
        </div>
        <div className="project-selector">
          <label>
            Projekt
            <select
              aria-label="Projekt"
              disabled={busy}
              value={project}
              onChange={(e) => selectProject(e.target.value)}
            >
              <option value="draft">{draftProject?.name ?? "Lokální návrh"} · bez repozitáře</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button onClick={() => setScreen("home")}>Nastavení projektu</button>
        {!localProject && (
          <button
            className="danger"
            disabled={busy}
            onClick={() => requestRemoval("project", project)}
          >
            Odebrat repozitář
          </button>
        )}
        <button onClick={() => setSettingsOpen(true)}>Nastavení plochy</button>
        <span className="local-status">LOKÁLNĚ · {location.port}</span>
      </header>
      <div className="modebar">
        <div className="modes">
          <button
            className={workspace === "main" ? "active" : ""}
            disabled={busy || localProject}
            onClick={() => {
              setWorkspace("main");
              enter(null);
            }}
          >
            Čistý main
          </button>
          <button
            className={workspace !== "main" ? "active" : ""}
            disabled={busy}
            onClick={() => {
              if (localProject) setWorkspace("draft");
              else if (view?.workspaces.length) {
                setWorkspace(view.workspaces[0].id);
                enter(null);
              } else open("workspace");
            }}
          >
            Pracovní prostor
          </button>
        </div>
        {activeWorkspace && (
          <select
            aria-label="Pracovní strom"
            value={workspace}
            disabled={busy}
            onChange={(e) => {
              setWorkspace(e.target.value);
              enter(null);
            }}
          >
            {view?.workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.actor} · {w.node_id}
              </option>
            ))}
          </select>
        )}
        <div className="revision">
          {localProject ? (
            "Návrh není schválený main"
          ) : (
            <>
              <code>
                {view?.branch ?? "načítání"} · {view?.sha?.slice(0, 12)}
              </code>
              {view?.dirty && (
                <span className="warn-text">Pracovní soubory změněny</span>
              )}
            </>
          )}
        </div>
        <button disabled={busy} onClick={() => run(refresh)}>
          Obnovit pohled
        </button>
        {!localProject && (
          <button
            disabled={busy}
            onClick={() => {
              if (
                window.confirm(
                  "Aktualizovat pouze čistou spravovanou kopii ze schváleného upstreamu? Žádný push.",
                )
              )
                run(async () => {
                  await api("/api/sync", { project, confirmed: true });
                  await bootstrap();
                });
            }}
          >
            Synchronizovat main
          </button>
        )}
      </div>
      {error && (
        <div className="error" role="alert">
          {error}
          <button aria-label="Zavřít chybu" onClick={() => setError("")}>
            ×
          </button>
        </div>
      )}
      <div className={"workspace-shell " + mode + "-mode"}>
        <nav className="mode-rail" aria-label="Pracovní módy">
          {(
            [
              ["structure", "Struktura", "◇"],
              ["text", "Text", "¶"],
              ["drawing", "Kreslení", "✎"],
              ["map", "Mapa", "⌘"],
            ] as const
          ).map(([key, label, icon]) => (
            <button
              key={key}
              aria-label={"Mód: " + label}
              aria-pressed={mode === key}
              onClick={() => setMode(key)}
            >
              <span>{icon}</span>
              {label}
            </button>
          ))}
        </nav>
        <aside className="tree workspace-tools">
          {mode === "drawing" ? (
            <DrawingTools
              wireframeMode={wireframeMode}
              onWireframeMode={setWireframeMode}
              onInsertWireframe={(kind) => setWireframeInsert((old) => ({ kind, sequence: (old?.sequence ?? 0) + 1 }))}
              tool={drawingTool}
              ready={drawingReady && editable}
              onTool={(type) =>
                setDrawingCommand((old) => ({
                  type,
                  sequence: old.sequence + 1,
                }))
              }
            />
          ) : mode === "map" ? (
            <>
              <div className="eyebrow">MAPA CELÉHO PROJEKTU</div>
              <h3>{activeProject?.name ?? "Lokální návrh"}</h3>
              <p className="muted">{view?.source}</p>
              {view?.graphStatus === "missing" && (
                <p role="status">
                  Repozitář nemá uložený graf. Tato mapa není automatická
                  analýza jeho souborů.
                </p>
              )}
              <p>
                Uzly:{" "}
                <strong data-testid="map-node-count">
                  {graph.nodes.length}
                </strong>
                <br />
                Propojení: {graph.edges.length}
              </p>
              <p className="muted">
                Přerušované čáry: struktura. Plné čáry: explicitní propojení.
                Dvojklik otevře uzel ve Struktuře.
              </p>
              <label className="field">
                Propojit z
                <select
                  aria-label="Propojit z"
                  value={linkSource}
                  onChange={(e) => setLinkSource(e.target.value)}
                >
                  <option value="">Vyber uzel</option>
                  {graph.nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Propojit do
                <select
                  aria-label="Propojit do"
                  value={linkTarget}
                  onChange={(e) => setLinkTarget(e.target.value)}
                >
                  <option value="">Vyber uzel</option>
                  {graph.nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                disabled={
                  !editable ||
                  !linkSource ||
                  !linkTarget ||
                  linkSource === linkTarget
                }
                onClick={() => connectGraph(linkSource, linkTarget)}
              >
                Propojit uzly
              </button>
              <button
                onClick={() =>
                  downloadArchify(graph, activeProject?.name ?? "Lokální návrh")
                }
              >
                Export pro Archify
              </button>
              <p className="muted">
                Export odráží tato data, nikoli odhad technologií ze zdrojového
                kódu.
              </p>
            </>
          ) : (
            <>
              <div className="eyebrow">STRUKTURA PROJEKTU</div>
              <button
                className={!parent ? "tree-row current" : "tree-row"}
                onClick={() => enter(null)}
              >
                ◇ {activeProject?.name ?? "Nové plátno"}
              </button>
              {graph.nodes
                .filter((n) => n.parentId === null)
                .map((n) => (
                  <button
                    key={n.id}
                    className={
                      "tree-row child " + (parent === n.id ? "current" : "")
                    }
                    onClick={() => enter(n.id)}
                  >
                    {n.kind === "sector" ? "▧" : "◈"} {n.name}
                  </button>
                ))}
              <div className="tree-help">
                Sektor → uzel → poduzel.
                <br />
                Každý uzel má vlastní plátno.
              </div>
              <div className="source-block">
                <div className="eyebrow">ZDROJ POHLEDU</div>
                <p>{view?.source ?? "Načítám pouze vybraný pohled…"}</p>
                {view && (
                  <small>
                    Pozorováno{" "}
                    {new Date(view.observedAt).toLocaleTimeString("cs-CZ")}
                  </small>
                )}
                {activeWorkspace && (
                  <>
                    <h4>Oddělený adresář</h4>
                    <code>{activeWorkspace.directory}</code>
                    <p>
                      Vlastník: {activeWorkspace.actor}. Tím není potvrzena
                      aktivita agenta.
                    </p>
                  </>
                )}
              </div>
              <div className="jobs">
                <div className="eyebrow">OPERACE</div>
                {jobs.length ? (
                  jobs.slice(0, 4).map((j) => (
                    <div className="job" key={j.id}>
                      <strong>
                        {j.kind} · {j.status}
                      </strong>
                      <p>{j.message}</p>
                    </div>
                  ))
                ) : (
                  <p>Žádná spuštěná Git operace.</p>
                )}
              </div>
            </>
          )}
        </aside>
        <main className="canvas-area">
          <div className="canvas-toolbar">
            <nav aria-label="Cesta plátnem">
              <button onClick={() => enter(null)}>Projekt</button>
              {ancestors.map((n) => (
                <span key={n.id}>
                  {" "}
                  / <button onClick={() => enter(n.id)}>{n.name}</button>
                </span>
              ))}
            </nav>
            {mode === "structure" && outsideLinks > 0 && (
              <button onClick={() => setMode("map")}>
                Vazby mimo vrstvu: {outsideLinks}
              </button>
            )}
            <div>
              <button
                disabled={!editable || (mode !== "structure" && mode !== "text")}
                onClick={() => open("sector")}
              >
                + Sektor
              </button>
              <button
                className="primary"
                disabled={!editable || (mode !== "structure" && mode !== "text")}
                onClick={() => open("node")}
              >
                + Uzel
              </button>
            </div>
          </div>
          <div className="canvas-surface">
            {view ? (
              mode === "text" ? (
                <TextWorkspace project={project} workspace={workspace} layer={layer} children={visible} targets={linkTargets} readOnly={!!view?.readOnly} onEnter={enter} onOpenNode={(id) => { openNode(id); setMode("structure"); }} onAgentTask={requestAgentTask} />
              ) : mode === "map" ? (
                <ProjectMap
                  graph={graph}
                  projectName={activeProject?.name ?? "Lokální návrh"}
                  selected={selected}
                  selectedEdge={selectedEdge}
                  settings={settings}
                  readOnly={!editable}
                  onSelect={(id) => {
                    setSelected(id);
                    setSelectedEdge(null);
                  }}
                  onSelectEdge={(id) => {
                    setSelectedEdge(id);
                    setSelected(null);
                  }}
                  onEnter={(id) => {
                    enter(id);
                    setMode("structure");
                  }}
                  onConnect={(c) => {
                    if (c.source && c.target) connectGraph(c.source, c.target);
                  }}
                />
              ) : mode === "drawing" ? (
                <WorkspaceBoundary
                  key={JSON.stringify([project, workspace, parent, mode])}
                  onExit={() => setMode("structure")}
                >
                  <Suspense
                    fallback={
                      <div className="loading">Načítám kreslicí nástroje…</div>
                    }
                  >
                    <DrawingWorkspace
                      wireframeMode={wireframeMode}
                      wireframeInsert={wireframeInsert}
                      key={JSON.stringify([project, workspace, parent])}
                      project={project}
                      workspace={workspace}
                      layer={parent ?? ""}
                      tool={drawingCommand.type}
                      toolSequence={drawingCommand.sequence}
                      settings={settings}
                      onTool={setDrawingTool}
                      onReady={setDrawingReady}
                    />
                  </Suspense>
                </WorkspaceBoundary>
              ) : (
                <Board
                  key={project + workspace + parent}
                  scope={project + workspace + parent}
                  graph={graph}
                  settings={settings}
                  parent={parent}
                  selected={selected}
                  disabled={!editable}
                  selectedEdge={selectedEdge}
                  onSelect={(id) => {
                    setSelected(id);
                    setSelectedEdge(null);
                  }}
                  onSelectEdge={(id) => {
                    setSelectedEdge(id);
                    setSelected(null);
                  }}
                  onEnter={enter}
                  editing={editingName}
                  onEditing={setEditingName}
                  onRename={(id, name) =>
                    run(() =>
                      save({
                        ...graph,
                        nodes: graph.nodes.map((n) =>
                          n.id === id ? { ...n, name } : n,
                        ),
                      }),
                    )
                  }
                  onCreateAt={(x, y) => {
                    if (!editable) return;
                    const created: CanvasNode = {
                      id: crypto.randomUUID(),
                      parentId: parent,
                      kind: "node",
                      name: "Nový uzel",
                      purpose: "",
                      x,
                      y,
                    };
                    run(async () => {
                      await save({ ...graph, nodes: [...graph.nodes, created] });
                      setSelected(created.id);
                      setEditingName(created.id);
                    });
                  }}
                  onPosition={(id, x, y) =>
                    run(() =>
                      save({
                        ...graph,
                        nodes: graph.nodes.map((n) =>
                          n.id === id ? { ...n, x, y } : n,
                        ),
                      }),
                    )
                  }
                  onConnect={(c) => {
                    if (c.source && c.target)
                      run(() =>
                        save({
                          ...graph,
                          edges: [
                            ...graph.edges,
                            {
                              id: crypto.randomUUID(),
                              source: c.source!,
                              target: c.target!,
                            },
                          ],
                        }),
                      );
                  }}
                />
              )
            ) : (
              <div className="loading" role="status">
                Načítám plátno…
              </div>
            )}
            {mode === "structure" && view && !visible.length && (
              <div className="empty-canvas">
                <div className="empty-symbol">＋</div>
                <h1>
                  {view.readOnly
                    ? "V mainu zatím není graf"
                    : "Prostor pro váš systém"}
                </h1>
                <p>
                  {view.readOnly
                    ? "Repozitář nemá verzovaný opora-canvas.json. Vytvořte pracovní prostor a připravte graf tam."
                    : "Začněte sektorem. Uvnitř vytvořte uzly, propojte je a popište jejich podstatu."}
                </p>
                {view.readOnly ? (
                  <button onClick={() => open("workspace")}>
                    Vytvořit pracovní prostor
                  </button>
                ) : (
                  <span>Prázdné plátno. Žádná ukázková data.</span>
                )}
              </div>
            )}
            {busy && (
              <div className="saving" role="status">
                Ukládám / ověřuji operaci…
              </div>
            )}
          </div>
          <footer>
            <span>
              {visible.length} uzlů v této vrstvě · {graph.nodes.length} v grafu
            </span>
            <span>
              {view?.readOnly
                ? "SCHVÁLENÁ VĚTEV · POUZE ČTENÍ"
                : "NÁVRH / PRACOVNÍ ZMĚNY"}{" "}
              · Agent se automaticky nespouští
            </span>
          </footer>
        </main>
        {mode === "drawing" || mode === "text" ? null : node ? (
          <NodePanel
            key={project + ":" + workspace + ":" + node.id + ":" + view?.digest}
            node={node}
            project={project}
            workspace={workspace}
            readOnly={!!view?.readOnly}
            busy={busy}
            workspaces={view?.workspaces ?? []}
            onEnter={() => {
              enter(node.id);
              if (mode === "map") setMode("structure");
            }}
            onDelete={() => requestRemoval("node", node.id)}
            onSave={(n) =>
              run(() =>
                save({
                  ...graph,
                  nodes: graph.nodes.map((old) => (old.id === n.id ? n : old)),
                }),
              )
            }
            onWorkspace={() => open("workspace")}
            onOpenNode={openNode}
            onAgentTask={() => requestAgentTask(node.id, node.purpose || node.name, "canvas")}
          />
        ) : edge ? (
          <aside className="detail">
            <div className="eyebrow">VAZBA · DETAIL</div>
            <h2>
              {graph.nodes.find((n) => n.id === edge.source)?.name} →{" "}
              {graph.nodes.find((n) => n.id === edge.target)?.name}
            </h2>
            <button
              className="danger wide"
              disabled={!editable}
              title={
                view?.readOnly
                  ? "Main je pouze pro čtení."
                  : "Zobrazit dopad před smazáním"
              }
              onClick={() => requestRemoval("edge", edge.id)}
            >
              Smazat vazbu
            </button>
          </aside>
        ) : (
          <aside className="detail idle">
            <div className="eyebrow">INSPEKTOR UZLU</div>
            <h2>
              Celý systém.
              <br />
              Jeden přesný uzel.
            </h2>
            <p>
              Vyberte uzel na plátně. Tady najdete jeho podstatu a přiřazené
              pracovní prostory.
            </p>
            <div className="flow-rule">
              <span>Schválený main</span>
              <i>↓</i>
              <span>Oddělený worktree</span>
              <i>↓</i>
              <span>Testy · review · PR</span>
              <i>↓</i>
              <span>Merge → synchronizace</span>
            </div>
            <p className="muted">
              Merge se řídí schválenými pravidly repozitáře. Toto plátno samo
              nepovoluje push ani spuštění agenta.
            </p>
            {!localProject && (
              <button onClick={() => open("workspace")}>
                Nový pracovní prostor
              </button>
            )}
          </aside>
        )}
      </div>
      {settingsOpen && (
        <WorkspaceSettings
          value={settings}
          onChange={updateSettings}
          onClose={() => setSettingsOpen(false)}
        />
      )}
      {removal && (
        <RemovalDialog
          key={removal.digest}
          preview={removal}
          onClose={() => setRemoval(null)}
          onConfirm={confirmRemoval}
        />
      )}
      {agentTask && <AgentTaskNotice request={agentTask} onDismiss={() => setAgentTask(null)} />}
      {modal && (
        <div className="modal-backdrop">
          <section
            role="dialog"
            aria-modal="true"
            aria-label="Nastavení operace"
            className="modal"
          >
            <button
              className="close"
              aria-label="Zavřít dialog"
              onClick={() => setModal(null)}
              disabled={busy}
            >
              ×
            </button>
            {modal === "github" ? (
              <>
                <div className="eyebrow">SCHVÁLENÝ ZDROJ</div>
                <h2>Připojit GitHub repozitář</h2>
                <p>
                  Vznikne samostatná spravovaná kopie s Git historií. Vaše
                  existující adresáře se nemění.
                </p>
                <label className="field">
                  GitHub URL
                  <input
                    aria-label="GitHub URL"
                    value={url}
                    onChange={(e) => {
                      setUrl(e.target.value);
                      setApproved(false);
                    }}
                    placeholder="https://github.com/vlastnik/repozitar"
                  />
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={approved}
                    onChange={(e) => setApproved(e.target.checked)}
                  />
                  Schvaluji tento zdroj pro klonování. Nepovoluji push ani
                  merge.
                </label>
                <button
                  className="primary"
                  disabled={!approved || busy}
                  onClick={() =>
                    run(async () => {
                      await api("/api/connect", { url, approved });
                      setModal(null);
                      await bootstrap();
                    })
                  }
                >
                  Připojit na pozadí
                </button>
                <p className="muted">
                  Privátní repo vyžaduje předem nastavený Git přístup na
                  serveru. Tokeny sem nevkládejte.
                </p>
              </>
            ) : modal === "workspace" ? (
              <>
                <h2>Oddělený pracovní prostor</h2>
                {localProject ? (
                  <p>
                    Nejdřív připojte schválený GitHub repozitář. Lokální návrh
                    se tím nesmaže.
                  </p>
                ) : (
                  <>
                    <p>
                      Nová větev a worktree vzniknou ze současného spravovaného
                      mainu. Vybraný uzel:{" "}
                      {node?.name ?? layer?.name ?? "kořen projektu"}.
                    </p>
                    <label className="field">
                      Vlastník / označení agenta
                      <input
                        aria-label="Vlastník pracovního prostoru"
                        value={actor}
                        onChange={(e) => setActor(e.target.value)}
                        maxLength={120}
                      />
                    </label>
                    <button
                      className="primary"
                      disabled={busy || !actor.trim()}
                      onClick={() =>
                        run(async () => {
                          const w = await api<Workspace>("/api/workspaces", {
                            project,
                            nodeId: node?.id ?? layer?.id ?? "project",
                            actor,
                          });
                          setWorkspace(w.id);
                          setModal(null);
                          enter(null);
                        })
                      }
                    >
                      Vytvořit worktree
                    </button>
                  </>
                )}
              </>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  run(async () => {
                    const siblings = visible.length;
                    const n: CanvasNode = {
                      id: crypto.randomUUID(),
                      parentId: parent,
                      kind: modal,
                      name,
                      purpose: "",
                      x: (siblings % 3) * 310,
                      y: Math.floor(siblings / 3) * 210,
                    };
                    await save({ ...graph, nodes: [...graph.nodes, n] });
                    setSelected(n.id);
                    setModal(null);
                  });
                }}
              >
                <div className="eyebrow">
                  {modal === "sector" ? "NOVÝ SEKTOR" : "NOVÝ UZEL"}
                </div>
                <h2>Jedno místo. Jasný účel.</h2>
                <label className="field">
                  Název uzlu
                  <input
                    aria-label="Název uzlu"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    maxLength={160}
                    autoFocus
                  />
                </label>
                <button className="primary" disabled={busy || !name.trim()}>
                  Vytvořit
                </button>
              </form>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
