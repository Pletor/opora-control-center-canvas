import { useMemo, useState } from "react";
import FlowEditor from "@/shared/flow-editor/components/FlowEditor";
import FlowCasesBar from "@/shared/flow-editor/flow-cases/components/FlowCasesBar";
import { addCase, caseFingerprint, caseMark, casesOf, removeCase, setCase } from "@/shared/flow-editor/flow-cases/logic/flow-cases";
import FlowPlayBar from "@/shared/flow-editor/flow-play/components/FlowPlayBar";
import { usePlay } from "@/shared/flow-editor/flow-play/logic/use-play";
import type { FlowGraph, FlowVersion } from "@/shared/flow-editor/logic/flow-types";
import { diffSummary, graphDiff } from "@/shared/flow-editor/logic/graph-diff";
import type { Project } from "@/shared/types/logic/types";
import LibraryVersionBar from "../library-versions/components/LibraryVersionBar";
import ProposalBar from "../library-versions/components/ProposalBar";
import { pendingProposal, pickFlowVersion } from "../library-versions/logic/library-versions";
import CommandBar from "../command-bar/components/CommandBar";
import DrawingBar from "../command-bar/components/DrawingBar";
import HeartWork from "../command-bar/components/HeartWork";
import EmptyPrompt from "../command-bar/components/EmptyPrompt";
import { showsEmptyPrompt } from "../command-bar/logic/empty-prompt";
import { commandNodeIds } from "../command-bar/logic/command-bar";
import { useCommandBar } from "../command-bar/logic/use-command-bar";
import BriefDialog from "../library-brief/components/BriefDialog";
import LibraryActions from "../library-actions/components/LibraryActions";
import { activateVersion, adoptFlow, contributeFlow, placeOf, promoteFlow, rejectVersion, rollbackFlow, saveFlowDraft } from "../logic/library-api";
import { learnedText, lineageOf } from "../logic/lineage";
import { useFlowChecks } from "../logic/use-flow-checks";
import { useLibraryFlow } from "../logic/use-library-flow";
import ElementContextHead from "../element-context/components/ElementContextHead";
import { LOGIC_PROMPT, logicCanvasTitle, planRoute } from "../element-context/logic/element-context";
import { useElementContext } from "../element-context/logic/use-element-context";
import "../styles/library-canvas.css";

const EMPTY: FlowGraph = { nodes: [], edges: [], notes: [], groups: [] };
const PLACE = { human: "Knihovna · Člověk", agent: "Knihovna · Agent", project: "Kopie v projektu" } as const;

/** Plátno toku v knihovně (`projectView=library&flow=<id>`): sdílený editor toků s katalogem „toky dat“, poznámkami,
 * rámci a inspektorem polí uzlu. Úprava se ukládá jako nový draft, draft se aktivuje bez schválení. Hlavička nese
 * rodokmen („vychází z …“, novější verze v knihovně) a akce převzetí, vylepšení a povýšení. Plátno se nespouští: pás
 * kontroly grafu ukazuje chyby serveru. Příkazový řádek (`/`, Ctrl+K, tlačítko „Zadání“) pošle zadání srdci a plátno
 * do jeho draftu samo načítá (`command-bar/`). U plátna člověka čeká návrh srdce (draft s poznámkou) s rozdílem proti aktivní
 * verzi a rozhodnutím Přijmout / Zamítnout; plátno agenta ukáže, kde se ho agent naučil. Rodič drží data a zápis,
 * dílky jen zobrazují a hlásí. Plátno logiky prvku plátna 2 (`opora:project-flow:<nodeId>` s prvkem) má v hlavičce
 * místo knihovny kontext prvku a návrat na plán stránky (`element-context/`). */
export default function LibraryCanvas({ flowId, project, workspace, projects, onOpenFlow, onBack, onOpenAssistant }: {
  flowId: string; project: string; workspace: string; projects: Project[]; onOpenFlow: (id: string) => void; onBack: () => void; onOpenAssistant?: () => void;
}) {
  const data = useLibraryFlow(flowId);
  const element = useElementContext(data.flow, project, workspace);
  const [viewId, setViewId] = useState<string | null>(null);
  const [edited, setEdited] = useState<FlowGraph | null>(null);
  const [node, setNode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const versions = useMemo(() => data.flow?.versions ?? [], [data.flow]);
  const viewing = pickFlowVersion(versions, viewId);
  const graph = edited ?? viewing?.graph ?? EMPTY;
  const checks = useFlowChecks(graph, data.types);
  const play = usePlay(graph);
  const [caseId, setCaseId] = useState<string | null>(null);
  const cases = casesOf(graph), current = cases.find((item) => item.id === caseId) ?? cases[0] ?? null;
  const marks = Object.fromEntries(cases.map((item) => [item.id, caseMark(play.results[item.id], caseFingerprint(graph, item))]));
  const place = data.flow ? placeOf(data.flow.ownerRef) : "human";
  const projectName = (id: string) => projects.find((item) => item.id === id)?.name ?? id;
  const lineage = data.flow ? lineageOf(data.flow, data.source, projectName) : null;
  const learned = place === "agent" ? learnedText(data.flow?.learnedFrom, projectName) : null;
  const proposal = place === "human" ? pendingProposal(versions) : null;
  const active = versions.find((item) => item.status === "active");
  const showsProposal = !!proposal && viewing?.id === proposal.id && !edited;
  const diff = useMemo(() => showsProposal && proposal ? graphDiff(active?.graph ?? EMPTY, proposal.graph) : null, [showsProposal, proposal, active]);

  const [picked, setPicked] = useState<readonly string[]>([]);
  const [briefOpen, setBriefOpen] = useState(false);
  const nodeIds = useMemo(() => commandNodeIds(node, picked, graph.nodes.map((item) => item.id)), [node, picked, graph.nodes]);
  const command = useCommandBar({ project, workspace, flowId, viewing, nodeIds, versions, reload: data.reload,
    onWrote: () => { if (!edited) setViewId(null); setNotice("Srdce nakreslilo návrh do draftu."); } });

  const emptyPrompt = showsEmptyPrompt(graph.nodes.length, play.active, command.phase !== "idle");

  const run = async <T,>(action: () => Promise<T>, done: (result: T) => void) => {
    setBusy(true);
    try { done(await action()); } catch (error) { setNotice(error instanceof Error ? error.message : String(error)); } finally { setBusy(false); }
  };
  const write = (action: () => Promise<FlowVersion>, text: string) => run(action, (version) => { setEdited(null); setViewId(version.id); setNotice(text); data.reload(); });
  const view = (id: string) => { if (edited && !window.confirm("Zahodit neuloženou úpravu?")) return; setEdited(null); setViewId(id); setNode(null); play.stop(); };

  if (data.loading && !data.flow) return <p className="library-canvas__empty">Načítám plátno toku…</p>;
  if (!data.flow) return <p className="library-canvas__empty" role="alert">{data.error || "Plátno toku neexistuje."} <button type="button" onClick={onBack}>← Zpět</button></p>;
  return <section className="library-canvas" aria-label="Plátno toku" data-testid="library-canvas">
    <header className="library-canvas__head">
      {element ? <ElementContextHead context={element} onBack={() => { history.replaceState(null, "", "/?" + planRoute(location.search, element)); onBack(); }}/>
        : <button type="button" className="library-canvas__back" onClick={onBack}>← Architektura</button>}
      <div className="library-canvas__title">
        <h2 className="library-canvas__name">{element ? logicCanvasTitle(element) : data.flow.title}<small className="library-canvas__place">{element ? "Logika prvku" : PLACE[place]}</small></h2>
        {data.flow.description && <p className="library-canvas__description">{data.flow.description}</p>}
        <p className="library-canvas__lineage" data-testid="library-lineage">
          {lineage?.from && <button type="button" className="library-canvas__link" disabled={!data.source} onClick={() => data.source && onOpenFlow(data.source.id)}>{lineage.from}</button>}
          {lineage?.newer && <span className="library-canvas__newer" data-testid="library-newer">{lineage.newer}</span>}
          {lineage?.derived && <span className="library-canvas__derived">{lineage.derived}</span>}
          {learned && <span className="library-canvas__learned" data-testid="library-learned">{learned}</span>}
        </p>
      </div>
      {notice && <span className="library-canvas__notice" role="status">{notice}</span>}
      {data.error && <span className="library-canvas__error" role="alert">{data.error}</span>}
      <LibraryActions place={place} title={data.flow.title} projects={projects} project={project} busy={busy} empty={!versions.length}
        onAdopt={(target, nodeId) => run(() => adoptFlow(flowId, target, nodeId), (copy) => { setNotice(`Převzato do projektu ${target}.`); onOpenFlow(copy.id); })}
        onContribute={(folder, slug, title) => run(() => contributeFlow(flowId, folder, slug, title), (made) => { setNotice("Uloženo do knihovny jako nový prvek."); onOpenFlow(made.id); })}
        onBrief={() => setBriefOpen(true)}
        onPromote={() => run(() => promoteFlow(flowId), () => { setNotice("Povýšeno do knihovny člověka."); data.reload(); })}/>
    </header>
    {proposal && <ProposalBar proposal={proposal} summary={diff && diffSummary(diff)} viewing={showsProposal} busy={busy} onView={() => view(proposal.id)}
      onAccept={() => write(() => activateVersion(proposal), `Návrh srdce přijat, v${proposal.n} je aktivní.`)}
      onReject={() => { const reason = window.prompt("Proč návrh srdce zamítnout?", "Návrh zamítnut člověkem."); if (reason?.trim()) write(() => rejectVersion(proposal.id, reason.trim()), "Návrh srdce zamítnut."); }}/>}
    {command.open && !emptyPrompt && <CommandBar initial={command.draft} selection={nodeIds} busy={command.busy} error={command.error} onSubmit={command.send} onClose={() => command.setOpen(false)}/>}
    {command.phase !== "idle" && <DrawingBar phase={command.phase} text={command.text} onDetails={() => command.setDetail(true)} onCancel={command.cancel} onOpenAssistant={onOpenAssistant}/>}
    <LibraryVersionBar versions={versions} viewing={viewing} dirty={!!edited} busy={busy} readOnly={false} onView={view} onDiscard={() => setEdited(null)}
      onSaveDraft={() => edited && write(() => saveFlowDraft(flowId, edited, viewing?.id ?? null), "Uloženo jako nový draft.")}
      onActivate={() => viewing && write(() => activateVersion(viewing), `Verze v${viewing.n} je aktivní.`)}
      onRollback={() => write(() => rollbackFlow(flowId), "Vráceno na předchozí verzi.")}/>
    {graph.nodes.length > 0 && <div className="library-canvas__run">
    <FlowCasesBar cases={cases} nodes={graph.nodes} selectedId={current?.id ?? null} marks={marks} disabled={play.active}
      onSelect={setCaseId} onAdd={() => { const made = addCase(graph); setEdited(made.graph); setCaseId(made.added.id); }}
      onRemove={(id) => setEdited(removeCase(graph, id))} onChange={(item) => setEdited(setCase(graph, item))}/>
    <FlowPlayBar play={play} canRun={!!current} onRun={() => current && play.run(current)}/>
    </div>}
    <div className="library-canvas__editor">
      {emptyPrompt && <EmptyPrompt {...(element ? LOGIC_PROMPT : {})} initial={command.draft} busy={command.busy} error={command.error} onSubmit={command.send}/>}
      <FlowEditor graph={graph} types={data.types} readOnly={false} diff={diff} selected={node} onSelect={setNode} onChange={setEdited}
        frames play={play} onPick={setPicked} tools={<button type="button" className="flow-editor__tool flow-editor__tool--primary" data-testid="library-command-open" title="Zadání pro srdce (klávesa / nebo Ctrl+K)" onClick={() => command.setOpen(true)}>Zadání</button>} nodePorts={checks.nodePorts} checkErrors={checks.errors ?? []}/>
      {command.phase !== "idle" && command.detail && <HeartWork phase={command.phase} work={command.work} elapsedMs={command.elapsedMs} typicalMs={command.typicalMs}
        onClose={() => command.setDetail(false)} onOpenAssistant={onOpenAssistant} onRetry={command.retry}/>}
    </div>
    {briefOpen && <BriefDialog flowId={flowId} version={viewing?.n ?? null} onClose={() => setBriefOpen(false)}/>}
  </section>;
}
