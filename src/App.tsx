import { useEffect, useRef, useState } from "react";
import Board from "./Board";
import NodePanel from "./NodePanel";
import {
  api,
  type Graph,
  type View,
  type Project,
  type Job,
  type CanvasNode,
  type Workspace,
} from "./types";
const initial = new URLSearchParams(location.search);
export default function App() {
  const [project, setProject] = useState(initial.get("project") ?? "draft");
  const [workspace, setWorkspace] = useState(
    initial.get("workspace") ?? "draft",
  );
  const [parent, setParent] = useState<string | null>(initial.get("layer"));
  const [selected, setSelected] = useState<string | null>(null);
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
    const b = await api<{ projects: Project[]; jobs: Job[] }>("/api/bootstrap");
    setProjects(b.projects);
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
    setSelected(null);
    setError("");
    refresh();
  }, [project, workspace]);
  useEffect(() => {
    const q = new URLSearchParams({ project, workspace });
    if (parent) q.set("layer", parent);
    history.replaceState(null, "", "/?" + q);
  }, [project, workspace, parent]);
  const completed = jobs
    .filter((j) => j.status === "complete" && j.project_id === project)
    .map((j) => j.id)
    .join(",");
  useEffect(() => {
    if (completed) refresh();
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
  const layer = graph.nodes.find((n) => n.id === parent);
  const editable = !!view && !view.readOnly && !busy;
  const visible = graph.nodes.filter((n) => n.parentId === parent);
  const ancestors: CanvasNode[] = [];
  let cursor = layer;
  while (cursor) {
    ancestors.unshift(cursor);
    cursor = graph.nodes.find((n) => n.id === cursor!.parentId);
  }
  const activeWorkspace = view?.workspaces.find((w) => w.id === workspace);
  const activeProject = projects.find((p) => p.id === project);
  function open(kind: typeof modal) {
    setModal(kind);
    setName("");
    setApproved(false);
  }
  function enter(id: string | null) {
    setParent(id);
    setSelected(null);
  }
  function selectProject(id: string) {
    setProject(id);
    setWorkspace(id === "draft" ? "draft" : "main");
    enter(null);
  }
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
              <option value="draft">Lokální návrh · bez repozitáře</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button onClick={() => open("github")}>Připojit GitHub</button>
        <span className="local-status">LOKÁLNĚ · 8740</span>
      </header>
      <div className="modebar">
        <div className="modes">
          <button
            className={workspace === "main" ? "active" : ""}
            disabled={busy || project === "draft"}
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
              if (project === "draft") setWorkspace("draft");
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
          {project === "draft" ? (
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
        {project !== "draft" && (
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
      <div className="workspace-shell">
        <aside className="tree">
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
                  Vlastník: {activeWorkspace.actor}. Tím není potvrzena aktivita
                  agenta.
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
            <div>
              <button disabled={!editable} onClick={() => open("sector")}>
                + Sektor
              </button>
              <button
                className="primary"
                disabled={!editable}
                onClick={() => open("node")}
              >
                + Uzel
              </button>
            </div>
          </div>
          <div className="canvas-surface">
            {view ? (
              <Board
                key={project + workspace + parent}
                scope={project + workspace + parent}
                graph={graph}
                parent={parent}
                selected={selected}
                disabled={!editable}
                onSelect={setSelected}
                onEnter={enter}
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
            ) : (
              <div className="loading" role="status">
                Načítám plátno…
              </div>
            )}
            {view && !visible.length && (
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
        {node ? (
          <NodePanel
            key={node.id + view?.digest}
            node={node}
            readOnly={!!view?.readOnly}
            busy={busy}
            workspaces={view?.workspaces ?? []}
            onEnter={() => enter(node.id)}
            onSave={(n) =>
              run(() =>
                save({
                  ...graph,
                  nodes: graph.nodes.map((old) => (old.id === n.id ? n : old)),
                }),
              )
            }
            onWorkspace={() => open("workspace")}
          />
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
            {project !== "draft" && (
              <button onClick={() => open("workspace")}>
                Nový pracovní prostor
              </button>
            )}
          </aside>
        )}
      </div>
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
                {project === "draft" ? (
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
