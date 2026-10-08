import { useSyncReport } from "../logic/use-sync-report";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DesktopState, SyncReport } from "@/shared/desktop-state/logic/types";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import type { SourceStatus } from "@/editor/canvas/node-card/logic/use-source-status";

import CardSource from "@/editor/canvas/node-card/components/CardSource";
import SourceRealization from "@/editor/canvas/node-card/components/SourceRealization";
import AssignmentWarning from "@/editor/canvas/node-card/components/AssignmentWarning";
import CardDesign from "@/editor/canvas/node-card/components/CardDesign";
import CardScenario from "@/editor/canvas/node-card/components/CardScenario";
import type { CardDnaBranchProps } from "./CardDnaAssignment";
import { assignmentStatusView, githubCommitUrl, syncStatusView } from "../logic/code-status";

/** Kód a verze: ukazuje jen doložený stav zdroje, zadání a reportu OporaHubu. */
export default function CardDnaCode({ node, data: rawData, state: _state, graph: _graph, project, workspace }: CardDnaBranchProps) {
  const data = rawData;
  const assignment = assignmentStatusView(data.assignmentStatus?.status);
  return <section className="card-dna__code" aria-label="Kód a verze">
    <h3>Kód a verze</h3>
    {data.source ? <CardSource {...data.source} /> : <p>Zdrojová cesta zatím není přiřazená.</p>}
    <SourceAvailability source={node.sourceRef} realization={node.realization} status={data.sourceStatus} />
    {data.realization && <SourceRealization nodeId={node.id} {...data.realization} mergePassed={data.evidence?.merge.status === "passed"} />}
    <section aria-label="Zadání versus výstup"><h3>Zadání vs. výstup</h3><p><b>{assignment.kind}</b> · {assignment.explanation}</p>
      {data.assignmentWarning && <AssignmentWarning {...data.assignmentWarning} />}</section>
    {node.design ?? data.view.design ? <section><h3>Návrh</h3><CardDesign design={node.design ?? data.view.design!} /></section> : <p>Návrh zatím není připojený.</p>}
    {data.scenario ? <section><h3>Scénář v prohlížeči</h3><CardScenario {...data.scenario} /></section> : <p>Scénář E2E zatím není nastavený.</p>}
    {project && workspace ? <SyncReportView project={project} workspace={workspace} nodeId={node.id} /> : <p>OporaHub nelze načíst bez projektu a pracovního prostoru.</p>}
  </section>;
}

function SourceAvailability({ source, realization, status }: { source: CanvasNode["sourceRef"]; realization: CanvasNode["realization"]; status?: SourceStatus }) {
  const label = source?.origin === "planned" && !source.path.trim() || status?.status === "unspecified" ? "cesta neurčena" : status?.status === "present" ? "existuje" : status?.status === "missing" ? "chybí" : status?.status === "unavailable" ? "nedostupný" : "nenačtený";
  const commitUrl = githubCommitUrl(realization?.prUrl, realization?.commit);
  return <section><h3>Zdroj</h3><p>sourceRef: {source ? `${source.origin} · ${source.path}` : "nepřiřazen"} · source-status: <b>{label}</b></p>
    {realization && <p>Commit <code>{realization.commit || "nedoloženo"}</code>{commitUrl && <> · <a href={commitUrl} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">GitHub commit</a></>} · ověřeno {realization.verifiedAt || "nikdy"}</p>}</section>;
}

function SyncReportView({ project, workspace, nodeId }: { project: string; workspace: string; nodeId: string }) {
  const { report, error } = useSyncReport(project, workspace);
  const status = syncStatusView(report, nodeId);
  return <section aria-label="OporaHub synchronizace"><h3>OporaHub</h3>{error ? <p role="alert">Synchronizaci nelze načíst: {error}</p> : !report ? <p role="status">Načítám synchronizační report…</p> : <><p><b>Stav: {status.kind}</b> · {status.explanation}</p>
    {status.signals.length ? <ul>{status.signals.map(signal => <li key={signal.id}>{signal.severity}: {signal.action} ({signal.evidence.expected} → {signal.evidence.actual})</li>)}</ul> : <p>Pro tuto kartu nejsou žádné signály.</p>}</>}</section>;
}
