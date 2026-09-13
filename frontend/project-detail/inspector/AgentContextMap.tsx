import type { CanvasNode, Graph } from "@/shared/types/types";
import "@/project-detail/inspector/agent-context-map.css";

export type ContextPacket = { id: string; digest: string; sizeBytes: number; scope?: { project: string; workspace: string; node: string }; excluded: unknown[]; truncated: unknown[]; sourceRefs: unknown[]; content: { focus?: { name?: string; nodeId?: string; purpose?: string; spec?: { fields?: Record<string, unknown> } }; neighbors?: unknown[]; journal?: unknown[] } };
type DiagramNode = { id: string; name: string; kind: CanvasNode["kind"]; parentId: string | null; sourceRef?: CanvasNode["sourceRef"] };
type DiagramEdge = { id: string; source: Pick<DiagramNode, "id" | "name">; target: Pick<DiagramNode, "id" | "name"> };
export type DesignContext = { focus: string; ancestry: DiagramNode[]; incoming: DiagramEdge[]; outgoing: DiagramEdge[] };

// Výstupní kopie: známé tvary klíčů se redigují, interní graf zůstává beze změny.
const SECRET_PATTERNS = [/AKIA[0-9A-Z]{16}/g, /github_pat_[A-Za-z0-9_-]{16,}/g, /gh[pousr]_[A-Za-z0-9]{36,}/g, /xox[baprs]-[A-Za-z0-9-]{10,}/g, /sk-[A-Za-z0-9_-]{20,}/g, /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g, /\b(api[_-]?key|secret|password|passwd|access[_-]?key|token)\b\s*[:=]\s*['"]?[A-Za-z0-9/+_.\-]{8,}['"]?/gi];
const redact = (value: string) => SECRET_PATTERNS.reduce((result, pattern) => result.replace(pattern, "[REDACTED]"), value);
const nodeForDiagram = (node: CanvasNode): DiagramNode => ({
  id: node.id, name: redact(node.name), kind: node.kind, parentId: node.parentId,
  sourceRef: node.sourceRef ? { origin: node.sourceRef.origin, kind: node.sourceRef.kind, path: redact(node.sourceRef.path) } : null,
});

function ancestry(graph: Graph, focus: string): DiagramNode[] {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const result: DiagramNode[] = []; const seen = new Set<string>(); let current = byId.get(focus);
  while (current && !seen.has(current.id)) { seen.add(current.id); result.unshift(nodeForDiagram(current)); current = current.parentId ? byId.get(current.parentId) : undefined; }
  return result;
}
export function snapshotDesignContext(graph: Graph, focus: string): DesignContext {
  const byId = new Map(graph.nodes.map((node) => [node.id, nodeForDiagram(node)]));
  const edgeForDiagram = (edge: Graph["edges"][number]): DiagramEdge => ({ id: edge.id, source: byId.get(edge.source) ?? { id: edge.source, name: "neznámý uzel" }, target: byId.get(edge.target) ?? { id: edge.target, name: "neznámý uzel" } });
  return { focus, ancestry: ancestry(graph, focus), incoming: graph.edges.filter((edge) => edge.target === focus).map(edgeForDiagram), outgoing: graph.edges.filter((edge) => edge.source === focus).map(edgeForDiagram) };
}
function sourceLabel(node: DiagramNode) {
  if (!node.sourceRef) return "legacy / bez uložené vazby na zdroj";
  const kind = node.sourceRef.kind === "file" ? "souboru" : "složky";
  const path = node.sourceRef.path || "cesta neurčena";
  return `${node.sourceRef.origin === "existing" ? "uložená vazba: existující" : "uložený návrh"} ${kind}: ${path} (stav souboru nyní neověřen)`;
}
function json(value: unknown) { return JSON.stringify(value, null, 2); }
export function packetMarkdown(packet: ContextPacket, designContext: DesignContext): string {
  const focus = packet.content.focus; const fields = focus?.spec?.fields ?? {}; const scope = packet.scope ?? { project: "", workspace: "", node: focus?.nodeId ?? "" };
  return ["# Kontextový paket OPORA", "", `- ID paketu: \`${packet.id}\``, `- Digest: \`${packet.digest}\``, `- Rozsah: \`${scope.project}/${scope.workspace}/${scope.node}\``, `- Velikost: ${packet.sizeBytes} UTF-8 bajtů`, "", "## Vybraný kontext", `- Název: ${focus?.name ?? "—"}`, `- Podstata: ${focus?.purpose ?? "—"}`, `- Cíl: ${String(fields.goal ?? "—")}`, `- Mimo rozsah: ${String(fields.non_goals ?? "—")}`, `- Podmínky dokončení: ${String(fields.acceptance ?? "—")}`, "", "## Vyloučené položky", "```json", json(packet.excluded), "```", "## Zkrácené položky", "```json", json(packet.truncated), "```", "## Ověřitelné reference zdrojů", "```json", json(packet.sourceRefs), "```", "## Diagramový kontext pro společný obraz", "Tento redigovaný lokální návrhový snapshot je mimo neměnný canvasPacket/digest. Diagramová spojení nejsou runtime závislosti ani důkaz volání a automaticky se nikam nedistribuují.", "```json", json(designContext), "```", "## Bezpečně serializovaný obsah paketu", "```json", json(packet.content), "```", "", "Tento neměnný snapshot se sám neposílá do LLM návrhu ani Codingu. Model vidí kontext, který dodá jeho harness; tento panel paket automaticky neposílá ani nečte soubory ze shelfu. Skryté uvažování se nezobrazuje."].join("\n");
}

export default function AgentContextMap({ graph, focus, packet, designContext }: { graph: Graph; focus: string; packet: ContextPacket | null; designContext?: DesignContext | null }) {
  const live = snapshotDesignContext(graph, focus); const snapshot = packet && designContext ? designContext : live; const fields = packet?.content.focus?.spec?.fields ?? {};
  return <details className="agent-context-map" open><summary><span role="heading" aria-level={2}>Mapa kontextu pro agenta</span></summary><div className="agent-context-map-body">
    <p className="muted">Instrukční mapa pro společný rozhovor člověka a agenta — ne telemetrie běhu, nákladů ani skrytého uvažování.</p>
    <p className="agent-context-flow">Zadání → Vybraný kontext → Návrh modelu → Nástroj / akce → Důkaz výsledku</p>
    <p className="agent-context-limits">Model vidí kontext, který dodá jeho harness; tento panel paket automaticky neposílá, nečte celý disk ani soubory ze shelfu. Model, běh, tokeny a náklady zde nejsou zapojené: jejich stav je neznámý.</p>
    <section aria-label="Ancestry vybraného kontextu"><h3>Vybraný kontext a předci</h3><ol data-testid="agent-context-ancestry" className="agent-context-ancestry">{snapshot.ancestry.length ? snapshot.ancestry.map((node) => <li key={node.id}><strong>{node.kind === "sector" ? "Sektor" : "Uzel"}: {node.name}</strong><small>{sourceLabel(node)}</small></li>) : <li>Žádný vybraný uzel — vyberte sektor nebo uzel pro mapu kontextu.</li>}</ol></section>
    <section aria-label="Diagramová spojení"><h3>Diagramová spojení vybraného uzlu</h3>{snapshot.focus && (snapshot.incoming.length || snapshot.outgoing.length) ? <div className="agent-context-edge-columns"><div><h4>Vstupní</h4><ul className="agent-context-edges">{snapshot.incoming.map((edge) => <li key={edge.id}>{edge.source.name} <code>({edge.source.id})</code> → vybraný uzel <small>diagramové spojení</small></li>)}</ul></div><div><h4>Výstupní</h4><ul className="agent-context-edges">{snapshot.outgoing.map((edge) => <li key={edge.id}>vybraný uzel → {edge.target.name} <code>({edge.target.id})</code><small>diagramové spojení</small></li>)}</ul></div></div> : <p className="muted">Žádné diagramové spojení pro vybraný uzel.</p>}<p className="agent-context-limits">Diagramové spojení není důkaz skutečného runtime volání ani závislosti. Mapa může popisovat zamýšlený systém, ne právě běžící kód.</p></section>
    {packet ? <section data-testid="context-packet-summary" className="agent-context-packet-summary" aria-label="Shrnutí neměnného paketu"><h3>Neměnný sestavený paket</h3><p><code>{packet.id}</code> · <code>{packet.digest}</code> · {packet.sizeBytes} UTF-8 bajtů</p><dl><dt>Cíl</dt><dd>{String(fields.goal ?? "—")}</dd><dt>Mimo rozsah</dt><dd>{String(fields.non_goals ?? "—")}</dd><dt>Podmínky dokončení</dt><dd>{String(fields.acceptance ?? "—")}</dd><dt>Vyloučeno / zkráceno</dt><dd>{packet.excluded.length} / {packet.truncated.length}</dd></dl></section> : <p className="muted">Sestavte paket pro neměnný snapshot zadání, sousedů a deníků.</p>}
  </div></details>;
}
