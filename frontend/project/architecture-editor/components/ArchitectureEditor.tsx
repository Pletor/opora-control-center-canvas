// Root theme first: piece styles loaded after it win equal-specificity ties.
import "../styles/architecture-editor.css";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type CanvasNode, type Graph, type RemovalPreview } from "@/shared/types/logic/types";
import { useDesktopState } from "@/shared/desktop-state/logic/state-store";
import type { NodePhase } from "@/shared/desktop-state/logic/types";
import { catalogPlacement, catalogPlan } from "@/editor/component-library/library-catalog/logic/catalog-plan";
import { itemById } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { editProductNode, sitePlan, type ProductDraft } from "@/project/product-tree/logic/product-tree";
import RemovalDialog from "@/ui-kit/removal-dialog/components/RemovalDialog";
import { discardSpecDrafts } from "@/editor/node-detail/assignment/components/NodeSpecEditor";
import { discardDrawingDrafts } from "@/editor/canvas/drawing/logic/drawing-state";
import { architectureEditorId, editorScopeNode, isEditorScopeClosed, moveEditorNode, growEditorArea, resizeEditorNode, connectEditorNodes, createEditorAreaPlan, setEditorEdgeCarries, setEditorNodeSection, setEditorPageSite } from "../logic/editor-model";
import { domainNode, domainForNode, domainPageTree, splitDomainHost, reorderDomainPage, reparentDomainPage } from "../logic/domain-model";
import { useArchitectureGraph } from "../logic/use-architecture-graph";
import { resolveEditorRoute } from "../logic/editor-route";
import { environmentOf, SHARED_GROUP } from "../page-editor/project-tree/logic/project-tree-model";
import ArchitectureLanding from "../landing/components/ArchitectureLanding";
import ArchitectureDomainMap from "../domain-map/components/ArchitectureDomainMap";
import PageEditor from "../page-editor/components/PageEditor";
import ComponentStructure from "../component-structure/components/ComponentStructure";
import ElementDetail from "../element-detail/components/ElementDetail";
import ArchitectureHeader from "./ArchitectureHeader";
import { useDomainLive } from "../logic/use-domain-live";
import { useDerivedJourneys } from "../logic/use-derived-journeys";
import { pageWork, panelViews } from "../logic/live-views";
import LiveDomainPanel from "../live-status/components/LiveDomainPanel";
import WebStatusBadge from "../live-status/components/WebStatusBadge";
import { sessionTitle, type CardRequest, type SessionRequest } from "../live-status/logic/session-state";
import { architectureEditable, contentLock, structureLock, type LockInput } from "../logic/edit-locks";
import { useWorktreeAdmin } from "../logic/use-worktree-admin";
import { normalizeConflicts } from "../view-conflicts/logic/view-conflicts";
import EditorNotices from "./EditorNotices";

/** Co editor architektury potřebuje vědět o živé práci: schopnost projektu (od App) a akce, které jdou nahoru do App. */
export type ArchitectureLiveProps = {
  worktreeLive: boolean; mainWorkspace: string;
  onSwitchWorkspace: (id: string) => void; onStartSession: (request: SessionRequest) => void; onCreateWorktree: (domainId: string) => void;
  /** Otevře kartu (App přepne prostor, je-li jiný) a relaci asistenta (panel Asistent). */
  onOpenCard: (request: CardRequest) => void; onOpenSession: (id: string) => void;
};

type Props = { project: string; workspace: string; projectName?: string; onGraphChanged: () => void; onOpenEditor: (id: string) => void; live: ArchitectureLiveProps };
export default function ArchitectureEditor({ project, workspace, projectName, onGraphChanged, onOpenEditor, live: liveProps }: Props) {
  const store = useArchitectureGraph(project, workspace, onGraphChanged);
  const desktop = useDesktopState(project, workspace);
  const [initial] = useState(() => { const route = new URLSearchParams(location.search); return (!route.has("project") || route.get("project") === project) && (!route.has("workspace") || route.get("workspace") === workspace) ? route : new URLSearchParams(); });
  const [ready, setReady] = useState(false);
  const [routeError, setRouteError] = useState("");
  const [domainId, setDomainId] = useState<string | null>(null);
  const [scopeId, setScopeId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [structureId, setStructureId] = useState<string | null>(null);
  const [error, setError] = useState("");
  /** One-shot: „+ Stránka“ in the project tree opens the map with this parent's new-page form already open. */
  const [draftParent, setDraftParent] = useState<string | null>(null);
  const [reveal, setReveal] = useState<string | null>(null);
  const [removal, setRemoval] = useState<RemovalPreview | null>(null);
  const [removing, setRemoving] = useState(false);
  const [worktreeId, setWorktreeId] = useState<string | null>(null);
  const live = useDomainLive(project, domainId, liveProps.worktreeLive);
  const admin = useWorktreeAdmin(project, () => { live.refreshWork(); onGraphChanged(); });
  const derivedJourneys = useDerivedJourneys(project, store.view?.digest);
  const graph = store.view?.graph ?? { nodes: [], edges: [] };
  const closed = new Set(Object.entries(desktop.state.nodes).filter(([, value]) => value.done?.confirmed).map(([id]) => id));
  const editorId = architectureEditorId(project, workspace, domainId ?? undefined);
  const active = useRef(scopeId); active.current = scopeId;
  const nodeStates = desktop.state.nodes;
  const phaseOf = useCallback((id: string): NodePhase => nodeStates[id]?.phase ?? "discover", [nodeStates]);
  const isDone = useCallback((id: string) => !!nodeStates[id]?.done?.confirmed, [nodeStates]);
  useEffect(() => {
    if (ready || !store.view) return;
    try {
      const route = resolveEditorRoute(graph, initial, project, workspace);
      setDomainId(route.domainId); setScopeId(route.pageId); setSelectedId(route.selectedId); setStructureId(route.structureId); setReady(true);
    } catch (cause) { setRouteError(cause instanceof Error ? cause.message : String(cause)); }
  }, [store.view, ready]);
  useEffect(() => {
    if (!ready || routeError) return;
    const params = new URLSearchParams(location.search); params.set("editorId", editorId);
    for (const [key, value] of [["domainId", domainId], ["pageId", scopeId], ["architectureNode", selectedId], ["structureNode", structureId]]) { if (value) params.set(key!, value); else params.delete(key!); }
    history.replaceState(null, "", "/?" + params);
  }, [ready, routeError, editorId, domainId, scopeId, selectedId, structureId]);
  // Editor is keyed by project only: a worktree switch keeps the route but drops a removal prepared against the previous workspace.
  useEffect(() => { setRemoval(null); setError(""); }, [workspace]);
  let domain: CanvasNode | null = null; let scope: CanvasNode | null = null; let scopeError = "";
  try { if (ready && domainId && store.view) { domain = domainNode(graph, domainId); scope = editorScopeNode(graph, scopeId); if (scope && domainForNode(graph, scope.id)?.id !== domain.id) throw new Error("Otevřená část již nepatří do této domény."); } }
  catch (cause) { scopeError = cause instanceof Error ? cause.message : String(cause); }
  // Struktura (domény, stránky) a obsah stránky mají vlastní zámek: na mainu jde měnit jen struktura (docs/domeny-a-worktree.md §4).
  const lockInput: LockInput = { loaded: !!store.view, loadError: store.error ?? "", ready, busy: store.busy, loading: store.loading, removing, removalOpen: !!removal, scopeError,
    architectureEditable: architectureEditable(store.view), readOnly: !!store.view?.readOnly, desktopLoading: desktop.loading, desktopError: desktop.error ?? "", desktopReadOnly: desktop.readOnly,
    // Jen nad ověřeným rozsahem: při přepnutí prostoru se graf načítá znovu a doména v něm chvíli chybí;
    // `isEditorScopeClosed` by na ni vyhodil výjimku uprostřed renderu a shodil celý editor (černá obrazovka).
    scopeClosed: !scopeError && domain !== null && isEditorScopeClosed(graph, scopeId ?? domainId, closed) };
  const locks = { structure: structureLock(lockInput), content: contentLock(lockInput) };
  const structureDisabled = !!locks.structure; const disabled = !!locks.content;
  const pages = domain ? domainPageTree(graph, domain.id) : [];
  const inDomain = (id: string | null) => graph.nodes.find((node) => node.id === id && domainForNode(graph, node.id)?.id === domainId);
  const selected = inDomain(selectedId);
  const structure = inDomain(structureId);
  function navigate(nextDomain: string | null, nextScope: string | null = null) { if (nextDomain !== domainId) setWorktreeId(null); setDomainId(nextDomain); setScopeId(nextScope); setSelectedId(nextScope); setStructureId(null); setReveal(null); setError(""); }
  function openScope(id: string) { try { editorScopeNode(graph, id); if (domainForNode(graph, id)?.id !== domainId) throw new Error("Prvek nepatří do této domény."); navigate(domainId, id === domainId ? null : id); } catch (cause) { setError(String(cause)); } }
  function openPage(nextDomain: string, pageId: string) { try { editorScopeNode(graph, pageId); if (domainForNode(graph, pageId)?.id !== nextDomain) throw new Error("Stránka nepatří k této doméně."); navigate(nextDomain, pageId); } catch (cause) { setError(String(cause)); } }
  function openStructure(id: string) { const node = inDomain(id); if (node && (node.kind === "node" || node.kind === "sector")) { setStructureId(id); setSelectedId(id); } }
  function writable(id: string | null = scopeId ?? domainId, kind: keyof typeof locks = "content") {
    const lock = locks[kind];
    if (lock || !store.view) throw new Error(lock?.text ?? "Tento rozsah nyní nelze upravovat.");
    if (domainId && id && domainForNode(graph, id)?.id !== domainId) throw new Error("Prvek již nepatří do otevřené domény. Obnovte mapu.");
    if (isEditorScopeClosed(graph, id, closed)) throw new Error("Tato karta nebo její předek je uzavřený.");
  }
  function subtreeIds(id: string) { const ids = new Set([id]); let added = true; while (added) { added = false; for (const node of graph.nodes) if (node.parentId && ids.has(node.parentId) && !ids.has(node.id)) { ids.add(node.id); added = true; } } return ids; }
  async function execute(action: () => Promise<void>) { setError(""); try { await action(); } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); throw cause; } }
  const eventAction = (action: () => Promise<void>) => { void execute(action).catch(() => {}); };
  async function saveGraph(next: Graph) { await store.saveGraph(next, store.view!.digest); }
  async function apply(plan: object, ref: string, target: string | null = null, kind: keyof typeof locks = "content") { writable(target ?? undefined, kind); const result = await store.applyPlan(plan, store.view!.digest); desktop.reload(); const node = result.view.graph.nodes.find((item) => item.id === result.refs[ref]); if (!node) throw new Error("Uložený prvek se nepodařilo načíst. Obnovte editor."); return node; }
  async function saveProduct(draft: ProductDraft) {
    await execute(async () => { writable(draft.id ?? draft.parentId, "structure");
      if (draft.id) { const current = graph.nodes.find((node) => node.id === draft.id); if (!current) throw new Error("Část projektu již neexistuje."); await saveGraph({ ...graph, nodes: graph.nodes.map((node) => node.id === draft.id ? editProductNode(current, draft) : node) }); }
      else { const created = await apply(sitePlan(draft), "component", draft.parentId, "structure"); if (created.site?.kind === "application") navigate(created.id); }
    });
  }
  /** New element stays on the page map; when it landed inside a card it is only selected, the map keeps its scope. */
  function created(start: string | null, node: CanvasNode) { if (active.current !== start) return; setSelectedId(node.id); if (node.parentId === start) setReveal(node.id); }
  async function insert(id: string, targetId: string | null = null, point?: { x: number; y: number }) {
    if (!scopeId) throw new Error("Nejdříve otevřete stránku."); writable(targetId ?? scopeId); const item = itemById(id); if (!item) throw new Error("Prvek není v katalogu.");
    const start = scopeId; created(start, await apply(catalogPlan(item, catalogPlacement(graph.nodes, scopeId, targetId, point)), "component", targetId ?? scopeId));
  }
  /** Sector parent may be an area: the plan places it inside the frame and keeps the area's own parent. */
  function createSector(parentId = scopeId) { eventAction(async () => { const start = scopeId; created(start, await apply({ nodes: [{ ref: "sector", kind: "sector", parent: parentId ? `@${parentId}` : null, name: "Nový sektor", purpose: "" }] }, "sector", parentId)); }); }
  function createNode(parentId: string) { eventAction(async () => { const start = scopeId; created(start, await apply({ nodes: [{ ref: "node", kind: "node", parent: `@${parentId}`, name: "Nový uzel", purpose: "" }] }, "node", parentId)); }); }
  function createArea(parentId = scopeId) { eventAction(async () => { const start = scopeId; created(start, await apply(createEditorAreaPlan(parentId), "area", parentId)); }); }
  function removalAllowed(ids: string[]) {
    const lock = structureLock({ ...lockInput, removalOpen: false }); // The open dialog itself must not block its own confirmation.
    if (lock) throw new Error(lock.text);
    for (const id of ids) { if (isEditorScopeClosed(graph, id, closed)) throw new Error("Odstranění obsahuje uzavřenou kartu. Nejdříve ji otevřete v Editoru."); if (domainForNode(graph, id)?.id !== domainId) throw new Error("Stránka obsahuje jinou doménu. Její odstranění z této mapy není povolené."); }
  }
  async function requestRemoval(id: string) { writable(id, "structure"); const preview = await api<RemovalPreview>("/api/removal-preview?" + new URLSearchParams({ project, workspace, kind: "node", target: id })); removalAllowed(preview.nodeIds); setRemoval(preview); }
  async function confirmRemoval(preview: RemovalPreview) {
    removalAllowed(preview.nodeIds);
    setRemoving(true);
    try { const result = await api<{ nodeIds?: string[] }>("/api/remove", { project, workspace, kind: preview.kind, target: preview.target, digest: preview.digest, confirmed: true });
      discardSpecDrafts(project, workspace, result.nodeIds ?? []); discardDrawingDrafts(project, workspace, result.nodeIds ?? []);
      setRemoval(null); if (scopeId && result.nodeIds?.includes(scopeId)) navigate(domainId); await store.reload(); desktop.reload(); onGraphChanged();
    } finally { setRemoving(false); }
  }
  function exportScope() {
    const ids = domainId ? new Set([...subtreeIds(scopeId ?? domainId)].filter((id) => domainForNode(graph, id)?.id === domainId)) : new Set(graph.nodes.filter((node) => node.site?.kind === "application").map((node) => node.id));
    const url = URL.createObjectURL(new Blob([JSON.stringify({ kind: "architecture-sketch", project, workspace, editorId, domainId, pageId: scopeId, graph: { nodes: graph.nodes.filter((node) => ids.has(node.id)), edges: graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)) } }, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "nacrt-architektury.json"; link.click(); URL.revokeObjectURL(url);
  }
  if (routeError) return <section className="architecture-editor ae-route-error" data-testid="architecture-route-error"><h2>Editor nelze otevřít</h2><p role="alert">{routeError}</p><button onClick={() => { setRouteError(""); setReady(true); navigate(null); }}>Otevřít seznam domén</button></section>;
  const env = domain ? environmentOf(domain) : null;
  const views = domain ? panelViews(live, domain.id) : null;
  const webBadge = views && <WebStatusBadge host={views.web.host} stale={views.web.stale}/>;
  const nav = { onOpenCard: liveProps.onOpenCard, onOpenSession: liveProps.onOpenSession };
  const crumbs = domain ? [env?.name ?? SHARED_GROUP, env?.host || domain.name, ...(scope ? [scope.name] : [])] : [];
  const identity = (original: CanvasNode, name: string, purpose: string) => execute(async () => { writable(original.id, original.site ? "structure" : "content"); const current = graph.nodes.find((node) => node.id === original.id); if (!current || current.name !== original.name || current.purpose !== original.purpose) throw new Error("Název nebo účel se mezitím změnil. Zrušte koncept a otevřete aktuální hodnoty."); await saveGraph({ ...graph, nodes: graph.nodes.map((node) => node.id === original.id ? { ...node, name: name.trim(), purpose: purpose.trim() } : node) }); });
  return <section className="architecture-editor" data-testid="standalone-architecture-editor">
    <ArchitectureHeader crumbs={crumbs} step={scope ? "Editor stránky" : domain ? "Mapa domény" : "Mapy architektury"} workspace={workspace} readOnly={!!store.view?.readOnly} editorId={editorId}
      back={domain ? { disabled: store.busy || removing, onClick: () => navigate(scope ? domain.id : null) } : null}
      pageTools={scope ? { disabled, onArea: () => createArea(), onSector: () => createSector() } : null}
      exportDisabled={!ready || !store.view} reloadDisabled={store.busy || removing} onExport={exportScope}
      onReload={() => eventAction(async () => { await store.reload(); desktop.reload(); })}
      onCopyId={() => { void navigator.clipboard.writeText(editorId).catch(() => setError("ID se nepodařilo zkopírovat.")); }}/>
    <EditorNotices error={error || (store.view ? store.error ?? "" : "") || desktop.error || ""} lock={scope ? locks.content : locks.structure} conflicts={normalizeConflicts(store.view?.conflicts)}/>
    {scopeError ? <div className="ae-route-error"><p role="alert">{scopeError}</p><button onClick={() => navigate(null)}>Zpět na domény</button></div> : !ready || !store.view ? <p className="ae-loading">Načítám architekturu…</p> : !domain ? <ArchitectureLanding graph={graph} disabled={structureDisabled} lockReason={locks.structure?.text}
      live={{ web: live.web, work: live.work, worktreeLive: live.worktreeLive, nav, onCreateWorktree: liveProps.onCreateWorktree, onStartMainSession: () => liveProps.onStartSession({ workspace: liveProps.mainWorkspace, nodeId: null, title: sessionTitle("main") }),
        onAssign: admin.assign, shelf: admin.shelf, onLoadShelf: admin.loadShelf }}
      onOpen={(id) => navigate(id)} onSave={saveProduct} onSplit={(id, host) => execute(async () => { writable(id, "structure"); const newId = crypto.randomUUID(); await saveGraph(splitDomainHost(graph, id, host, newId)); navigate(newId); })}/>
    : !scope ? <ArchitectureDomainMap key={domain.id} domain={domain} initialDraftParentId={draftParent} onDraftOpened={() => setDraftParent(null)} pages={pages} disabled={structureDisabled} onOpen={openScope}
      work={pageWork(graph, live, domain.id, worktreeId)} derivedJourneys={derivedJourneys}
      webBadge={views && !views.work ? webBadge : null}
      live={views?.work ? <LiveDomainPanel web={views.web} work={views.work} announcement={live.announcement} selectedWorktreeId={worktreeId} onSelectWorktree={setWorktreeId} onRefreshWeb={live.refreshWeb} nav={nav}
        actions={{ currentWorkspace: workspace, onSwitch: liveProps.onSwitchWorkspace, onStartSession: liveProps.onStartSession, onArchive: async (id, reason) => { await admin.archive(id, reason); setWorktreeId((current) => (current === id ? null : current)); } }} onCreateWorktree={() => liveProps.onCreateWorktree(domain.id)}/> : null} onSave={saveProduct} onRemove={(id) => eventAction(() => requestRemoval(id))}
      onReorder={(id, direction) => eventAction(async () => { writable(id, "structure"); const next = reorderDomainPage(graph, domain.id, id, direction); next.nodes.forEach((node, index) => { if (graph.nodes[index]?.id !== node.id) writable(node.id, "structure"); }); await saveGraph(next); })}
      onReparent={(id, parentId) => execute(async () => { for (const child of subtreeIds(id)) writable(child, "structure"); writable(parentId, "structure"); await saveGraph(reparentDomainPage(graph, domain.id, id, parentId)); })}/>
    : <PageEditor key={domain.id + ":" + scope.id} webBadge={webBadge} graph={graph} domain={domain} scope={scope} projectName={projectName || "Projekt"} selectedId={selected?.id ?? null}
      editorId={editorId} disabled={disabled} structureDisabled={structureDisabled} reveal={reveal} onOpenPage={openPage} onAddPage={(id) => { navigate(id); setDraftParent(id); }} onOpenScope={openScope}
      onSelect={setSelectedId} onOpenStructure={openStructure} onOpenEditor={onOpenEditor} onArea={() => createArea()} onSector={(id) => createSector(id)} onAddNode={createNode}
      onInsert={(id, target, point) => eventAction(() => insert(id, target, point))}
      onMove={(id, x, y, area) => execute(async () => { writable(id); if (area) writable(area.id); const next = moveEditorNode(area ? growEditorArea(graph, area) : graph, id, x, y); for (const moved of next.nodes) { const prior = graph.nodes.find((node) => node.id === moved.id); if (prior && (prior.x !== moved.x || prior.y !== moved.y)) writable(moved.id); } await saveGraph(next); })}
      onConnect={(source, target) => eventAction(async () => { writable(source); writable(target); await saveGraph(connectEditorNodes(graph, source, target, crypto.randomUUID())); })}
      onResize={(id, w, h) => execute(async () => { writable(id); const next = resizeEditorNode(graph, id, w, h); if (next !== graph) await saveGraph(next); })}
      structure={structure ? <ComponentStructure graph={graph} rootId={structure.id} selectedId={selected?.id ?? null} phaseOf={phaseOf} isDone={isDone} disabled={disabled}
        onSelect={setSelectedId} onOpen={openStructure} onAddNode={createNode} onAddSector={(id) => createSector(id)} onAddArea={(id) => createArea(id)} onClose={() => setStructureId(null)}/> : null}
      detail={selected ? <ElementDetail project={project} workspace={workspace} graph={graph} nodeId={selected.id} domainId={domain.id} phase={phaseOf(selected.id)} done={isDone(selected.id)}
        disabled={selected.site ? structureDisabled : disabled} onIdentity={identity} onOpenEditor={onOpenEditor} onSelect={setSelectedId} onClose={() => setSelectedId(null)}
        onCarries={(edgeId, carries) => eventAction(async () => { const edge = graph.edges.find((item) => item.id === edgeId); if (edge) { writable(edge.source); writable(edge.target); } await saveGraph(setEditorEdgeCarries(graph, edgeId, carries)); })}
        onSection={(nodeId, section) => eventAction(async () => { writable(nodeId); await saveGraph(setEditorNodeSection(graph, nodeId, section)); })}
        onPage={(original, site) => execute(async () => { writable(original.id, "structure"); const next = setEditorPageSite(graph, original, site); if (next !== graph) await saveGraph(next); })}/> : null}/>}
    {removal && <RemovalDialog preview={removal} onClose={() => setRemoval(null)} onConfirm={confirmRemoval}/>}
  </section>;
}
