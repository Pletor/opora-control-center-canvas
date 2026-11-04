import { useMemo, useState } from "react";
import FlowEditor from "@/shared/flow-editor/components/FlowEditor";
import type { FlowGraph, FlowVersion } from "@/shared/flow-editor/logic/flow-types";
import type { Project } from "@/shared/types/logic/types";
import LibraryVersionBar from "../library-versions/components/LibraryVersionBar";
import { pickFlowVersion } from "../library-versions/logic/library-versions";
import LibraryActions from "../library-actions/components/LibraryActions";
import { activateVersion, adoptFlow, contributeFlow, placeOf, promoteFlow, rollbackFlow, saveFlowDraft } from "../logic/library-api";
import { lineageOf } from "../logic/lineage";
import { useFlowChecks } from "../logic/use-flow-checks";
import { useLibraryFlow } from "../logic/use-library-flow";
import "../styles/library-canvas.css";

const EMPTY: FlowGraph = { nodes: [], edges: [], notes: [], groups: [] };
const PLACE = { human: "Knihovna · Člověk", agent: "Knihovna · Agent", project: "Kopie v projektu" } as const;

/** Plátno toku v knihovně (`projectView=library&flow=<id>`): sdílený editor toků s katalogem „toky dat“, poznámkami,
 * rámci a inspektorem polí uzlu. Úprava se ukládá jako nový draft, draft se aktivuje bez schválení. Hlavička nese
 * rodokmen („vychází z …“, novější verze v knihovně) a akce převzetí, vylepšení a povýšení. Plátno se nespouští: pás
 * kontroly grafu ukazuje chyby serveru. Rodič drží data a zápis, dílky jen zobrazují a hlásí. */
export default function LibraryCanvas({ flowId, project, projects, onOpenFlow, onBack }: {
  flowId: string; project: string; projects: Project[]; onOpenFlow: (id: string) => void; onBack: () => void;
}) {
  const data = useLibraryFlow(flowId);
  const [viewId, setViewId] = useState<string | null>(null);
  const [edited, setEdited] = useState<FlowGraph | null>(null);
  const [node, setNode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const versions = useMemo(() => data.flow?.versions ?? [], [data.flow]);
  const viewing = pickFlowVersion(versions, viewId);
  const graph = edited ?? viewing?.graph ?? EMPTY;
  const checks = useFlowChecks(graph, data.types);
  const place = data.flow ? placeOf(data.flow.ownerRef) : "human";
  const lineage = data.flow ? lineageOf(data.flow, data.source, (id) => projects.find((item) => item.id === id)?.name ?? id) : null;

  const run = async <T,>(action: () => Promise<T>, done: (result: T) => void) => {
    setBusy(true);
    try { done(await action()); } catch (error) { setNotice(error instanceof Error ? error.message : String(error)); } finally { setBusy(false); }
  };
  const write = (action: () => Promise<FlowVersion>, text: string) => run(action, (version) => { setEdited(null); setViewId(version.id); setNotice(text); data.reload(); });
  const view = (id: string) => { if (edited && !window.confirm("Zahodit neuloženou úpravu?")) return; setEdited(null); setViewId(id); setNode(null); };

  if (data.loading && !data.flow) return <p className="library-canvas__empty">Načítám plátno toku…</p>;
  if (!data.flow) return <p className="library-canvas__empty" role="alert">{data.error || "Plátno toku neexistuje."} <button type="button" onClick={onBack}>← Zpět</button></p>;
  return <section className="library-canvas" aria-label="Plátno toku" data-testid="library-canvas">
    <header className="library-canvas__head">
      <button type="button" className="library-canvas__back" onClick={onBack}>← Architektura</button>
      <div className="library-canvas__title">
        <h2 className="library-canvas__name">{data.flow.title}<small className="library-canvas__place">{PLACE[place]}</small></h2>
        {data.flow.description && <p className="library-canvas__description">{data.flow.description}</p>}
        <p className="library-canvas__lineage" data-testid="library-lineage">
          {lineage?.from && <button type="button" className="library-canvas__link" disabled={!data.source} onClick={() => data.source && onOpenFlow(data.source.id)}>{lineage.from}</button>}
          {lineage?.newer && <span className="library-canvas__newer" data-testid="library-newer">{lineage.newer}</span>}
          {lineage?.derived && <span className="library-canvas__derived">{lineage.derived}</span>}
        </p>
      </div>
      {notice && <span className="library-canvas__notice" role="status">{notice}</span>}
      {data.error && <span className="library-canvas__error" role="alert">{data.error}</span>}
      <LibraryActions place={place} title={data.flow.title} projects={projects} project={project} busy={busy} empty={!versions.length}
        onAdopt={(target, nodeId) => run(() => adoptFlow(flowId, target, nodeId), (copy) => { setNotice(`Převzato do projektu ${target}.`); onOpenFlow(copy.id); })}
        onContribute={(folder, slug, title) => run(() => contributeFlow(flowId, folder, slug, title), (made) => { setNotice("Uloženo do knihovny jako nový prvek."); onOpenFlow(made.id); })}
        onPromote={() => run(() => promoteFlow(flowId), () => { setNotice("Povýšeno do knihovny člověka."); data.reload(); })}/>
    </header>
    <LibraryVersionBar versions={versions} viewing={viewing} dirty={!!edited} busy={busy} readOnly={false} onView={view} onDiscard={() => setEdited(null)}
      onSaveDraft={() => edited && write(() => saveFlowDraft(flowId, edited, viewing?.id ?? null), "Uloženo jako nový draft.")}
      onActivate={() => viewing && write(() => activateVersion(viewing), `Verze v${viewing.n} je aktivní.`)}
      onRollback={() => write(() => rollbackFlow(flowId), "Vráceno na předchozí verzi.")}/>
    <div className="library-canvas__editor">
      <FlowEditor graph={graph} types={data.types} readOnly={false} selected={node} onSelect={setNode} onChange={setEdited}
        frames nodePorts={checks.nodePorts} checkErrors={checks.errors ?? []}/>
    </div>
  </section>;
}
