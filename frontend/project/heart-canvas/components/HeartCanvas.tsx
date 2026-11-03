import { useMemo, useState } from "react";
import FlowEditor from "@/shared/flow-editor/components/FlowEditor";
import type { FlowGraph } from "@/shared/flow-editor/logic/flow-types";
import { diffSummary, graphDiff } from "@/shared/flow-editor/logic/graph-diff";
import { runOverlay } from "@/shared/flow-editor/logic/run-overlay";
import RunList from "../run-list/components/RunList";
import { runRows, stallRows, type StallRow } from "../run-list/logic/run-list";
import RunLogPanel from "../run-log/components/RunLogPanel";
import { logRows } from "../run-log/logic/log-view";
import VersionBar from "../version-bar/components/VersionBar";
import { defaultCompare, versionChips } from "../version-bar/logic/version-bar";
import { pickVersion, proposeCandidate, saveDraft } from "../logic/heart-api";
import { useHeartData } from "../logic/use-heart-data";
import { useRunDetail } from "../logic/use-run-detail";
import "../styles/heart-canvas.css";

type Mode = "editor" | "runs";
const AUTO = "auto";

/** Plátno 1 – srdce projektu: graf verze workflow srdce v generickém editoru toků. Editor upravuje graf a ukládá ho
 * jen jako nový draft (a draft navrhne ke evalu jako kandidáta), Běhy ukazují vybraný běh na jeho verzi jen ke čtení
 * se stavy uzlů, prostoji a logem synchronizovaným s plátnem. Rodič drží data, výběr a zápis; dílky jen zobrazují. */
export default function HeartCanvas({ project }: { project: string }) {
  const data = useHeartData(project);
  const [mode, setMode] = useState<Mode>("editor");
  const [viewId, setViewId] = useState<string | null>(null);
  const [compare, setCompare] = useState<string | null>(AUTO);
  const [edited, setEdited] = useState<FlowGraph | null>(null);
  const [node, setNode] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [onlyVersion, setOnlyVersion] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const detail = useRunDetail(mode === "runs" ? runId : null);

  const runVersion = mode === "runs" ? detail.run?.workflow_version_id ?? null : null;
  const viewing = pickVersion(data.versions, runVersion ?? viewId);
  const compareId = compare === AUTO ? defaultCompare(data.versions, viewing) : compare;
  const base = data.versions.find((item) => item.id === compareId && item.id !== viewing?.id) ?? null;
  const graph = (mode === "editor" ? edited : null) ?? viewing?.graph ?? { nodes: [], edges: [] };
  const diff = useMemo(() => base && mode === "editor" ? graphDiff(base.graph, graph) : null, [base, graph, mode]);
  const overlay = useMemo(() => runOverlay(mode === "runs" ? detail.run?.node_runs ?? [] : [], data.stalls), [mode, detail.run, data.stalls]);
  const stalls = useMemo(() => stallRows(data.stalls, data.versions), [data.stalls, data.versions]);
  const rows = useMemo(() => runRows(data.runs, data.versions, data.stalls, onlyVersion ? viewing?.id ?? null : null), [data.runs, data.versions, data.stalls, onlyVersion, viewing]);
  const log = useMemo(() => logRows(detail.events, detail.run?.node_runs ?? []), [detail.events, detail.run]);

  const view = (id: string) => { if (edited && !window.confirm("Zahodit neuloženou úpravu?")) return; setEdited(null); setViewId(id); setCompare(AUTO); setNode(null); };
  const write = async (action: () => Promise<{ id: string }>, done: string) => {
    setBusy(true);
    try { const version = await action(); setEdited(null); setViewId(version.id); setCompare(AUTO); setNotice(done); data.reload(); }
    catch (error) { setNotice(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  };
  const openStall = (stall: StallRow) => { setMode("runs"); setRunId(stall.runId); setNode(stall.nodeId); };

  if (data.loading && !data.workflow) return <p className="heart-canvas__empty">Načítám srdce projektu…</p>;
  if (!data.workflow) return <p className="heart-canvas__empty">{data.error || "Projekt zatím nemá workflow srdce (kind heart)."}</p>;
  return <section className="heart-canvas" aria-label="Plátno srdce" data-testid="heart-canvas">
    <header className="heart-canvas__head">
      <h2 className="heart-canvas__title">{data.workflow.name}<small className="heart-canvas__scope">{data.workflow.project_id ? "workflow projektu" : "sdílené workflow"}</small></h2>
      <nav className="heart-canvas__modes" aria-label="Pohled plátna srdce">
        <button type="button" className="heart-canvas__mode" aria-pressed={mode === "editor"} onClick={() => setMode("editor")}>Editor</button>
        <button type="button" className="heart-canvas__mode" aria-pressed={mode === "runs"} onClick={() => { setMode("runs"); setRunId(runId ?? rows[0]?.id ?? null); }}>
          Běhy{stalls.length ? ` · ${stalls.length} prostoj` : ""}</button>
      </nav>
      {notice && <span className="heart-canvas__notice" role="status">{notice}</span>}
      {data.error && <span className="heart-canvas__error" role="alert">{data.error}</span>}
    </header>
    <VersionBar chips={versionChips(data.versions, viewing?.id ?? null)} compareId={base?.id ?? null} diffText={diff ? diffSummary(diff) : ""}
      editing={mode === "editor"} dirty={!!edited} canPropose={!edited && viewing?.status === "draft"} busy={busy || mode === "runs"}
      onView={view} onCompare={setCompare} onDiscard={() => setEdited(null)}
      onSaveDraft={() => edited && write(() => saveDraft(data.workflow!.id, edited, viewing?.id ?? null), "Uloženo jako nový draft.")}
      onPropose={() => viewing && write(() => proposeCandidate(viewing.id), "Draft navržen ke evalu jako kandidát.")}/>
    <div className="heart-canvas__body">
      {mode === "runs" && <RunList rows={rows} stalls={stalls} selected={runId} onlyVersion={onlyVersion}
        onSelect={(id) => { setRunId(id); setNode(null); }} onStall={openStall} onOnlyVersion={setOnlyVersion}/>}
      <div className="heart-canvas__editor">
        <FlowEditor graph={graph} types={data.types} readOnly={mode === "runs"} overlay={overlay} diff={diff} nodeRuns={detail.run?.node_runs ?? []}
          selected={node} onSelect={setNode} onChange={setEdited}/>
      </div>
    </div>
    {mode === "runs" && <RunLogPanel rows={log} selectedNode={node} error={detail.error} onSelectNode={setNode}/>}
  </section>;
}
