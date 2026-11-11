// Root theme first: piece styles loaded after it win equal-specificity ties.
import "../styles/architecture-editor.css";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type CanvasNode, type ElementKind, type Graph, type PageSection, type RemovalPreview } from "@/shared/types/logic/types";
import { useDesktopState } from "@/shared/desktop-state/logic/state-store";
import type { NodePhase } from "@/shared/desktop-state/logic/types";
import { editProductNode, sitePlan, type ProductDraft } from "@/project/product-tree/logic/product-tree";
import RemovalDialog from "@/ui-kit/removal-dialog/components/RemovalDialog";
import { discardSpecDrafts } from "@/editor/node-detail/assignment/components/NodeSpecEditor";
import { discardDrawingDrafts } from "@/editor/canvas/drawing/logic/drawing-state";
import { architectureEditorId, editorScopeNode, isEditorScopeClosed, createEditorElementPlan, setEditorEdgeCarries, setEditorNodeSection, setEditorPageLayout, setEditorPageSite } from "../logic/editor-model";
import type { ScanProposal } from "../page-editor/plan-scan/logic/page-scan";
import { adoptScan as adoptScanParts, type AdoptParts } from "../page-editor/plan-scan/logic/adopt-scan";
import { scanAdoptDeps } from "../page-editor/plan-scan/logic/scan-adopt-deps";
import { domainNode, domainForNode, domainEntryPage, splitDomainHost, reorderDomainPage } from "../logic/domain-model";
import { useArchitectureGraph } from "../logic/use-architecture-graph";
import { edgeRemovalPreviewUrl, edgeRemovalRequest } from "../logic/edge-removal";
import { resolveEditorRoute } from "../logic/editor-route";
import { activePageId, environmentOf, isSharedDomain, SHARED_GROUP } from "../page-editor/project-tree/logic/project-tree-model";
import { pageComplete } from "../page-editor/logic/plan-progress";
import ArchitectureLanding from "../landing/components/ArchitectureLanding";
import { environmentAddress, isMobileDomain } from "../landing/logic/domain-kind";
import PageEditor from "../page-editor/components/PageEditor";
import ElementDetail from "../element-detail/components/ElementDetail";
import ArchitectureHeader from "./ArchitectureHeader";
import { useDomainLive } from "../logic/use-domain-live";
import { useStudioRuns } from "@/project/studio/logic/use-studio-runs";
import { useCardLife } from "../card-state/logic/use-card-life";
import { useMapWorktrees } from "../logic/use-map-worktrees";
import { useCardGuards } from "@/project/studio/studio-guards/logic/use-card-guards";
import ProjectFlowsProvider from "@/project/project-flows/components/ProjectFlowsProvider";
import { useMapCheck } from "../logic/use-map-check";
import { mapCheckGroups, type MapCheckTarget } from "../domain-site/map-check/logic/map-check";
import { panelViews } from "../logic/live-views";
import WebStatusBadge from "../live-status/components/WebStatusBadge";
import type { ArchitectureLiveProps } from "../logic/live-props";
import { architectureSketch } from "../logic/architecture-sketch";
import { architectureEditable, contentLock, structureLock, type LockInput } from "../logic/edit-locks";
import { useWorktreeAdmin } from "../logic/use-worktree-admin";
import { normalizeConflicts } from "../view-conflicts/logic/view-conflicts";
import EditorNotices from "./EditorNotices";
import { usePageIntents } from "@/project/intent-canvas/intent-entry/logic/use-page-intents";
import { pageDecomposeOffer, type PageDecompose } from "../page-editor/page-decompose/logic/page-decompose-prompt";

export type { ArchitectureLiveProps } from "../logic/live-props";

const EMPTY_GRAPH: Graph = { nodes: [], edges: [] };
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
  const [error, setError] = useState("");
  /** Kompletní stránky, které člověk v tomto sezení otevřel k úpravám (trvalé uzavření je další krok kontraktu). */
  const [reopened, setReopened] = useState<ReadonlySet<string>>(new Set());
  const [removal, setRemoval] = useState<RemovalPreview | null>(null);
  const [removing, setRemoving] = useState(false);
  const live = useDomainLive(project, domainId, liveProps.worktreeLive);
  const admin = useWorktreeAdmin(project, () => { live.refreshWork(); onGraphChanged(); });
  const derivedJourneys = useStudioRuns(project, store.view?.digest).journeys;
  const mapCheck = useMapCheck(project, store.view?.digest);
  const intents = usePageIntents(project, store.view?.digest);
  const graph = store.view?.graph ?? EMPTY_GRAPH;
  const guards = useCardGuards(project, workspace);
  const worktrees = useMapWorktrees(project, liveProps.worktreeLive, store.view?.digest);
  const cards = useCardLife({ graph, nodes: desktop.state.nodes, work: live.work.data, check: mapCheck, derived: derivedJourneys, guards, worktrees });
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
      setDomainId(route.domainId); setScopeId(route.pageId); setSelectedId(route.selectedId); setReady(true);
    } catch (cause) { setRouteError(cause instanceof Error ? cause.message : String(cause)); }
  }, [store.view, ready]);
  useEffect(() => {
    if (!ready || routeError) return;
    const params = new URLSearchParams(location.search); params.set("editorId", editorId);
    for (const [key, value] of [["domainId", domainId], ["pageId", scopeId], ["architectureNode", selectedId]]) { if (value) params.set(key!, value); else params.delete(key!); }
    params.delete("structureNode");
    history.replaceState(null, "", "/?" + params);
  }, [ready, routeError, editorId, domainId, scopeId, selectedId]);
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
  // Plátno 2 otevře doménu na první stránce; doména bez stránky (nebo sdílená struktura) zůstane bez rozsahu.
  useEffect(() => { if (domain && !scopeId && !removing && !store.loading && !isSharedDomain(domain)) { const entry = domainEntryPage(graph, domain.id); if (entry) { setScopeId(entry); setSelectedId(entry); } } }, [domain?.id, scopeId, removing, store.loading, store.view]);
  const activePage = scope ? activePageId(graph, scope.id) : null;
  const complete = !!activePage && pageComplete(graph, activePage, cards.states);
  const sealed = complete && !reopened.has(activePage!);
  const baseContent = contentLock(lockInput);
  const locks = { structure: structureLock(lockInput), content: baseContent ?? (sealed ? { text: "Stránka je kompletní. Otevřete ji k úpravám.", transient: false } : null) };
  const structureDisabled = !!locks.structure; const disabled = !!locks.content;
  const inDomain = (id: string | null) => graph.nodes.find((node) => node.id === id && domainForNode(graph, node.id)?.id === domainId);
  const selected = inDomain(selectedId);
  function navigate(nextDomain: string | null, nextScope: string | null = null) { setDomainId(nextDomain); setScopeId(nextScope); setSelectedId(nextScope); setError(""); }
  function openScope(id: string) { try { editorScopeNode(graph, id); if (domainForNode(graph, id)?.id !== domainId) throw new Error("Prvek nepatří do této domény."); navigate(domainId, id === domainId ? null : id); } catch (cause) { setError(String(cause)); } }
  /** Klik na díru plánu: stránka se otevře, komponenta a hrana otevřou stránku a vyberou prvek (u hrany její zdroj). */
  function openFinding(target: MapCheckTarget) { if (target.kind === "journey") return; openScope(target.kind === "page" ? target.id : target.pageId); if (target.kind !== "page") setSelectedId(target.kind === "node" ? target.id : target.sourceId); }
  function writable(id: string | null = scopeId ?? domainId, kind: keyof typeof locks = "content") {
    const lock = locks[kind];
    if (lock || !store.view) throw new Error(lock?.text ?? "Tento rozsah nyní nelze upravovat.");
    if (domainId && id && domainForNode(graph, id)?.id !== domainId) throw new Error("Prvek již nepatří do otevřené domény. Obnovte mapu.");
    if (isEditorScopeClosed(graph, id, closed)) throw new Error("Tato karta nebo její předek je uzavřený.");
  }
  async function execute(action: () => Promise<void>) { setError(""); try { await action(); } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); throw cause; } }
  const eventAction = (action: () => Promise<void>) => { void execute(action).catch(() => {}); };
  async function saveGraph(next: Graph) { await store.saveGraph(next, store.view!.digest); }
  async function apply(plan: object, ref: string, target: string | null = null, kind: keyof typeof locks = "content") { writable(target ?? undefined, kind); const result = await store.applyPlan(plan, store.view!.digest); desktop.reload(); const node = result.view.graph.nodes.find((item) => item.id === result.refs[ref]); if (!node) throw new Error("Uložený prvek se nepodařilo načíst. Obnovte editor."); return node; }
  async function saveProduct(draft: ProductDraft) {
    await execute(async () => { writable(draft.id ?? draft.parentId, "structure");
      if (draft.id) { const current = graph.nodes.find((node) => node.id === draft.id); if (!current) throw new Error("Část projektu již neexistuje."); await saveGraph({ ...graph, nodes: graph.nodes.map((node) => node.id === draft.id ? editProductNode(current, draft) : node) }); }
      else { const created = await apply(sitePlan(draft), "component", draft.parentId, "structure"); if (created.site?.kind === "application") navigate(created.id); else if (created.site?.kind === "page") navigate(domainId, created.id); }
    });
  }
  /** Prvek logiky z palety do boxu (`section`) nebo na celou stránku; plán přenese `card.section` (`createEditorElementPlan`). */
  function insertElement(pageId: string, kind: ElementKind, label: string, section: string | null) { eventAction(async () => { const start = scopeId; const node = await apply(createEditorElementPlan(pageId, kind, section, label), "element", pageId); if (active.current === start) setSelectedId(node.id); }); }
  /** Layout stránky (zámek struktury, u inspirace boxu obsahu) jednou změnou grafu; prvky odebraných boxů přejdou na celou stránku (zámek obsahu). */
  function saveLayout(pageId: string, sections: PageSection[], lock: "structure" | "content" = "structure") { eventAction(async () => { writable(pageId, lock); const next = setEditorPageLayout(graph, pageId, sections); next.touched.forEach((id) => writable(id)); if (next.graph !== graph) await saveGraph(next.graph); }); }
  /** Převzetí skenu po částech (Layout, Design, Logika a tok dat); zápisy grafu jdou přes `store` s čerstvým digestem po každém kroku
   * (`scanAdoptDeps`), selhání jedné části nezahodí ostatní a výsledek každé části ukáže panel skenu. */
  const adoptScan = async (pageId: string, proposal: ScanProposal, scanId: string, parts: AdoptParts) => {
    setError("");
    try { return await adoptScanParts(proposal, parts, scanAdoptDeps({ project, workspace, pageId, scanId, store, contentLock: locks.content?.text ?? null, writable })); }
    // Layout jde přes `/api/page-plan` mimo `store`: bez znovunačtení by plátno ukazovalo starý layout a další zápis narazil na 409.
    finally { await store.reload().catch(() => undefined); desktop.reload(); onGraphChanged(); }
  };
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
      setRemoval(null); if (scopeId && result.nodeIds?.some((id) => id === scopeId || id === activePage)) navigate(domainId); await store.reload(); desktop.reload(); onGraphChanged();
    } finally { setRemoving(false); }
  }
  /** Vazba jde pryč náhledem a potvrzením bez dialogu: nenese obsah karty a server ji umí vrátit (`recoveryId`). */
  function removeEdge(edgeId: string) {
    eventAction(async () => { const edge = graph.edges.find((item) => item.id === edgeId); if (!edge) throw new Error("Vazba již neexistuje."); writable(edge.source); writable(edge.target);
      setRemoving(true);
      try { const preview = await api<RemovalPreview>(edgeRemovalPreviewUrl({ project, workspace }, edgeId)); await api("/api/remove", edgeRemovalRequest({ project, workspace }, edgeId, preview)); await store.reload(); desktop.reload(); onGraphChanged(); }
      finally { setRemoving(false); } });
  }
  function exportScope() {
    const url = URL.createObjectURL(new Blob([JSON.stringify({ kind: "architecture-sketch", project, workspace, editorId, domainId, pageId: scopeId, graph: architectureSketch(graph, domainId, scopeId) }, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "nacrt-architektury.json"; link.click(); URL.revokeObjectURL(url);
  }
  if (routeError) return <section className="architecture-editor ae-route-error" data-testid="architecture-route-error"><h2>Editor nelze otevřít</h2><p role="alert">{routeError}</p><button onClick={() => { setRouteError(""); setReady(true); navigate(null); }}>Otevřít seznam domén</button></section>;
  const env = domain ? environmentOf(domain) : null;
  const views = domain ? panelViews(live, domain.id) : null;
  const webBadge = views && domain && !isMobileDomain(domain) && <WebStatusBadge host={views.web.host} stale={views.web.stale}/>;
  const nav = { onOpenCard: liveProps.onOpenCard };
  const decompose: PageDecompose = (pageId) => pageDecomposeOffer({ project, workspace, graph, pageId, check: mapCheck });
  const crumbs = domain ? [env?.name ?? SHARED_GROUP, environmentAddress(env) || domain.name, ...(scope ? [scope.name] : [])] : [];
  const identity = (original: CanvasNode, name: string, purpose: string) => execute(async () => { writable(original.id, original.site ? "structure" : "content"); const current = graph.nodes.find((node) => node.id === original.id); if (!current || current.name !== original.name || current.purpose !== original.purpose) throw new Error("Název nebo účel se mezitím změnil. Zrušte koncept a otevřete aktuální hodnoty."); await saveGraph({ ...graph, nodes: graph.nodes.map((node) => node.id === original.id ? { ...node, name: name.trim(), purpose: purpose.trim() } : node) }); });
  return <ProjectFlowsProvider project={project} workspace={workspace} digest={store.view?.digest} onOpen={liveProps.onOpenLibraryFlow}><section className="architecture-editor" data-testid="standalone-architecture-editor">
    <ArchitectureHeader crumbs={crumbs} step={domain ? "Plán stránky" : "Mapy architektury"} workspace={workspace} readOnly={!!store.view?.readOnly} editorId={editorId}
      back={domain ? { disabled: store.busy || removing, onClick: () => navigate(null) } : null}
      exportDisabled={!ready || !store.view} reloadDisabled={store.busy || removing} onExport={exportScope}
      onReload={() => eventAction(async () => { await store.reload(); desktop.reload(); })}
      onCopyId={() => { void navigator.clipboard.writeText(editorId).catch(() => setError("ID se nepodařilo zkopírovat.")); }}/>
    <EditorNotices error={error || (store.view ? store.error ?? "" : "") || desktop.error || ""} lock={domain ? baseContent : locks.structure} conflicts={normalizeConflicts(store.view?.conflicts)}/>
    {scopeError ? <div className="ae-route-error"><p role="alert">{scopeError}</p><button onClick={() => navigate(null)}>Zpět na domény</button></div> : !ready || !store.view ? <p className="ae-loading">Načítám architekturu…</p> : !domain ? <ArchitectureLanding project={project} workspace={workspace} graph={graph} disabled={structureDisabled} lockReason={locks.structure?.text}
      live={{ web: live.web, work: live.work, worktreeLive: live.worktreeLive, nav, onCreateWorktree: liveProps.onCreateWorktree,
        onAssign: admin.assign, shelf: admin.shelf, onLoadShelf: admin.loadShelf }}
      onOpen={(id) => navigate(id)} onOpenFlow={liveProps.onOpenLibraryFlow} onManageSite={liveProps.onOpenSite} onSave={saveProduct} onSplit={(id, host) => execute(async () => { writable(id, "structure"); const newId = crypto.randomUUID(); await saveGraph(splitDomainHost(graph, id, host, newId)); navigate(newId); })}/>
    : isSharedDomain(domain) ? <div className="ae-route-error" data-testid="architecture-shared-domain"><p role="alert">Doména {domain.name} je starší sdílená struktura s více hosty. Plán stránky má vždy jedna doména; oddělte host na přehledu domén.</p><button onClick={() => navigate(null)}>Otevřít přehled domén</button></div>
    : <PageEditor key={domain.id} project={project} workspace={workspace} webBadge={webBadge} graph={graph} domain={domain} scope={scope} selectedId={selected?.id ?? null}
      disabled={disabled} structureDisabled={structureDisabled} lockText={{ structure: locks.structure?.text ?? null, content: locks.content?.text ?? null, drawing: locks.content?.transient ? undefined : locks.content?.text ?? null }} onOpenPage={openScope} onAdoptScan={adoptScan} onOpenSite={liveProps.onOpenSite}
      cards={cards} decompose={decompose} check={mapCheck && mapCheckGroups(mapCheck, graph, domain)} onOpenFinding={openFinding}
      complete={complete} sealed={sealed} onReopen={() => { if (activePage) setReopened((set) => new Set(set).add(activePage)); }}
      tree={{ intent: liveProps.onOpenIntent && { intents, onOpen: liveProps.onOpenIntent }, onSave: saveProduct, onRemove: (id) => eventAction(() => requestRemoval(id)),
        onReorder: (id, direction) => eventAction(async () => { writable(id, "structure"); const next = reorderDomainPage(graph, domain.id, id, direction); next.nodes.forEach((node, index) => { if (graph.nodes[index]?.id !== node.id) writable(node.id, "structure"); }); await saveGraph(next); }) }}
      onSelect={setSelectedId} onOpenEditor={onOpenEditor} onLayout={saveLayout} onInsertElement={insertElement}
      onMoveElement={(nodeId, section) => eventAction(async () => { writable(nodeId); await saveGraph(setEditorNodeSection(graph, nodeId, section)); })}
      onRemoveElement={(id) => eventAction(async () => { writable(id); await requestRemoval(id); })}
      detail={selected ? <ElementDetail project={project} workspace={workspace} graph={graph} nodeId={selected.id} domainId={domain.id} phase={phaseOf(selected.id)} done={isDone(selected.id)}
        disabled={selected.site ? structureDisabled : disabled} onIdentity={identity} onOpenEditor={onOpenEditor} onSelect={setSelectedId} onClose={() => setSelectedId(null)}
        onCarries={(edgeId, carries) => eventAction(async () => { const edge = graph.edges.find((item) => item.id === edgeId); if (edge) { writable(edge.source); writable(edge.target); } await saveGraph(setEditorEdgeCarries(graph, edgeId, carries)); })}
        onRemoveEdge={removeEdge}
        onSection={(nodeId, section) => eventAction(async () => { writable(nodeId); await saveGraph(setEditorNodeSection(graph, nodeId, section)); })}
        onPage={(original, site) => execute(async () => { writable(original.id, "structure"); const next = setEditorPageSite(graph, original, site); if (next !== graph) await saveGraph(next); })}/> : null}/>}
    {removal && <RemovalDialog preview={removal} onClose={() => setRemoval(null)} onConfirm={confirmRemoval}/>}
  </section></ProjectFlowsProvider>;
}
