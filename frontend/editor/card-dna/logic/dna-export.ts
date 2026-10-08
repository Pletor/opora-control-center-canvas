import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import type { AcceptedResult } from "@/editor/llm-control/editor-context/logic/handoff";

export type DnaExportInput = { node: CanvasNode; data: NodeCardData; state: DesktopState; graph: Graph; brief?: Record<string, unknown> | null; results: AcceptedResult[]; messages?: Record<string, unknown>[]; partialHistory: boolean };
const record = (value: unknown): Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const shown = (value: unknown) => value === undefined || value === null || value === "" ? "nedoloženo" : String(value);
const json = (data: unknown) => JSON.stringify(data ?? null, null, 2);

/** Markdown drží zdrojové objekty doslovně; z nich lze obnovit kartu bez domýšlení plochých polí. */
export function buildDnaExport(input: DnaExportInput): string {
  const { node, data, state, graph, brief, results, messages = [], partialHistory } = input; const briefData = record(brief); const workflow = state.nodes[node.id] ?? null;
  const decisions = state.decisions.filter(item => item.nodeId === node.id); const paths = [node.sourceRef?.path, ...decisions.map(item => item.path)].filter((item): item is string => !!item);
  const assignment = briefData.assignment ?? briefData.goal ?? null; const evidence = data.evidence; const checks = evidence?.checksRun ?? [];
  const reconstruction = { brief: briefData, messages, node: { canvas: node, brief: briefData.node ?? null }, workflow, blocks: briefData.blocks ?? [], rules: { boundaries: briefData.boundaries ?? null, state: state.rules }, notes: { pipeline: workflow?.stages?.items ?? [], content: briefData.content ?? null }, decisions: { card: decisions, brief: record(briefData.context).decisions ?? [] }, proofs: { cardEvidence: evidence ?? null, briefEvidence: briefData.evidence ?? null, realization: node.realization ?? null }, specification: briefData.specification ?? null, assignment, graph: { edges: graph.edges.filter(edge => edge.source === node.id || edge.target === node.id) }, resultSnapshots: results };
  return [
    `# DNA karty: ${node.name}`, "", `- id: ${node.id}`, `- účel: ${shown(node.purpose)}`,
    "", "## Zadání", "```json", json({ assignment, specification: briefData.specification ?? null }), "```",
    "", "## Pipeline", ...(workflow?.stages?.items?.length ? workflow.stages.items.map(stage => `- ${shown(stage.title)} — ${shown(stage.note || stage.status)}${stage.retryOf ? ` (opakování ${stage.retryOf})` : ""}`) : ["- —"]),
    "", "## Důkazy", ...(["tests", "review", "merge"] as const).map(kind => `- ${kind}: ${record(evidence)[kind] ? json(record(evidence)[kind]) : "—"}`), ...(checks.length ? checks.map(run => `- ${shown(run.checkId)}: ${shown(run.command)} · exit ${shown(run.exitCode)} · ${shown(run.at)}${run.logUrl ? ` · ${run.logUrl}` : ""}`) : ["- běhy kontrol: —"]),
    "", "## Rozhodnutí", ...(decisions.length ? decisions.map(item => `- ${shown(item.createdAt)} · ${shown(item.by)}: ${shown(item.text)}${item.path ? ` (${item.path})` : ""}`) : ["- —"]),
    "", "## Historie agentů", ...(results.length ? results.map(item => `- ${shown(item.createdAt)} · ${shown(item.agent)} · ${shown(item.binding)}\n~~~json\n${json(item)}\n~~~`) : ["- —"]), ...(partialHistory ? ["", "⚠ Historie agentů není kompletní (výsledky nebo předávky zpráv): jsou načtené jen dosavadní stránky."] : []),
    "", "## Předávky zpráv", "```json", json(messages), "```",
    "", "## Realizace", `- commit: ${shown(node.realization?.commit)}`, `- pull request: ${shown(node.realization?.prUrl)}`, `- ověřeno: ${shown(node.realization?.verifiedAt)}`,
    "", "## Cesty a návaznosti", ...(paths.length ? paths.map(path => `- ${path}`) : ["- —"]),
    "", "## Rekonstrukční data", "```json", json(reconstruction), "```",
  ].join("\n");
}
