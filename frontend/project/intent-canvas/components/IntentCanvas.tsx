import { useMemo, useState } from "react";
import FlowEditor from "@/shared/flow-editor/components/FlowEditor";
import type { FlowGraph, FlowVersion } from "@/shared/flow-editor/logic/flow-types";
import { proposeCandidate } from "@/project/heart-canvas/logic/heart-api";
import IntentVersionBar from "../intent-versions/components/IntentVersionBar";
import { diffCounts, diffText, diffToActive, EMPTY_GRAPH, intentLane, pickIntentVersion } from "../intent-versions/logic/intent-versions";
import { approveVersion, rejectVersion, saveIntentDraft } from "../logic/intent-api";
import { useIntentData } from "../logic/use-intent-data";
import "../styles/intent-canvas.css";

/** Plátno 2 – záměr stránky: graf workflow `page_intent` stránky ve sdíleném editoru toků s katalogem záměru. Úprava se
 * ukládá jako nový draft (první uložení workflow založí), draft jde navrhnout ke schválení a kandidáta schválí nebo
 * zamítne člověk. Rodič drží data, výběr a zápis; lišta verzí a editor jen zobrazují a hlásí. */
export default function IntentCanvas({ project, page, onBack }: { project: string; page: string; onBack: () => void }) {
  const data = useIntentData(project, page);
  const [viewId, setViewId] = useState<string | null>(null);
  const [edited, setEdited] = useState<FlowGraph | null>(null);
  const [node, setNode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const lane = useMemo(() => intentLane(data.versions), [data.versions]);
  const viewing = pickIntentVersion(data.versions, lane, viewId);
  const graph = edited ?? viewing?.graph ?? EMPTY_GRAPH;
  const diff = useMemo(() => data.versions.length ? diffToActive(lane, viewing, graph) : null, [data.versions, lane, viewing, graph]);

  const view = (id: string) => { if (edited && !window.confirm("Zahodit neuloženou úpravu?")) return; setEdited(null); setViewId(id); setNode(null); };
  const write = async (action: () => Promise<FlowVersion>, done: string) => {
    setBusy(true);
    try { const version = await action(); setEdited(null); setViewId(version.id); setNotice(done); data.reload(); }
    catch (error) { setNotice(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  };

  if (data.loading && !data.types.length) return <p className="intent-canvas__empty">Načítám záměr stránky…</p>;
  return <section className="intent-canvas" aria-label="Plátno záměru stránky" data-testid="intent-canvas">
    <header className="intent-canvas__head">
      <button type="button" className="intent-canvas__back" onClick={onBack}>← Architektura</button>
      <h2 className="intent-canvas__title">Záměr stránky<small className="intent-canvas__page">{data.workflow?.name ?? `stránka ${page} · zatím bez záměru, první uložení ho založí`}</small></h2>
      {notice && <span className="intent-canvas__notice" role="status">{notice}</span>}
      {data.error && <span className="intent-canvas__error" role="alert">{data.error}</span>}
    </header>
    <IntentVersionBar lane={lane} viewingId={viewing?.id ?? null} diffText={diff ? diffText(diffCounts(diff)) : ""} dirty={!!edited} busy={busy}
      onView={view} onDiscard={() => setEdited(null)}
      onSaveDraft={() => edited && write(() => saveIntentDraft(data.workflow, project, page, edited, viewing?.id ?? null), "Uloženo jako nový draft.")}
      onPropose={() => viewing && write(() => proposeCandidate(viewing.id), "Draft navržen ke schválení.")}
      onApprove={() => viewing && write(() => approveVersion(viewing.id), "Záměr schválen, je aktivní.")}
      onReject={(reason) => viewing && write(() => rejectVersion(viewing.id, reason), "Kandidát zamítnut.")}/>
    <div className="intent-canvas__editor">
      <FlowEditor graph={graph} types={data.types} readOnly={false} diff={diff} selected={node} onSelect={setNode} onChange={setEdited}/>
    </div>
  </section>;
}
