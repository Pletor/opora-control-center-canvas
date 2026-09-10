import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type Graph } from "./types";
import AgentContextMap, { packetMarkdown, snapshotDesignContext, type ContextPacket, type DesignContext } from "./AgentContextMap";
import PlanPanel from "./PlanPanel";
import CodingPanel from "./CodingPanel";
import TaskHandoffPanel from "./TaskHandoffPanel";
import type { WorkspaceSelection } from "./workspace-selection";

/** packet = jediný hlavní vstup Podklady pro agenta; ostatní panely jsou pokročilé nástroje. */
export type WorkbenchPane = "packet" | "context" | "plan" | "coding" | "task";

function downloadText(name: string, value: string, type: string) {
  const url = URL.createObjectURL(new Blob([value], { type }));
  const link = document.createElement("a");
  link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url);
}

/** packet = napojený AgentPacketPanel (Sonnet); bez něj slouží hlavnímu vstupu skutečný stávající builder paketu. */
export default function EditorWorkbench({ project, workspace, nodeId, graph, selection, open, pane, onPane, onClose, packet: packetPanel = null }: {
  project: string; workspace: string; nodeId: string; graph: Graph; selection: WorkspaceSelection;
  open: boolean; pane: WorkbenchPane; onPane: (pane: WorkbenchPane) => void; onClose: () => void; packet?: ReactNode;
}) {
  const [visited, setVisited] = useState(new Set<WorkbenchPane>());
  const [focus, setFocus] = useState(nodeId);
  const [neighbors, setNeighbors] = useState<string[]>([]);
  const [days, setDays] = useState("");
  const [maxBytes, setMaxBytes] = useState(32000);
  const [packet, setPacket] = useState<ContextPacket | null>(null);
  const [designContext, setDesignContext] = useState<DesignContext | null>(null);
  const [validation, setValidation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestSerial = useRef(0);
  const currentScope = useRef("");
  const scopeKey = JSON.stringify([project, workspace]);
  currentScope.current = scopeKey;
  function invalidatePacket() {
    requestSerial.current += 1;
    setPacket(null); setDesignContext(null); setValidation(""); setBusy(false); setError("");
  }
  useEffect(() => { if (open) setVisited((old) => new Set(old).add(pane)); }, [open, pane]);
  useEffect(() => { setFocus(nodeId); setNeighbors([]); setDays(""); invalidatePacket(); }, [nodeId, scopeKey]);
  useEffect(() => { if (packet) invalidatePacket(); }, [graph]);
  const validMaxBytes = Number.isInteger(maxBytes) && maxBytes >= 1000 && maxBytes <= 500000;
  async function build() {
    if (!focus || !validMaxBytes) return;
    const serial = ++requestSerial.current;
    const buildScope = currentScope.current;
    const selectedDesignContext = snapshotDesignContext(graph, focus);
    const includeJournalDays = days.split(",").map((day) => day.trim()).filter(Boolean);
    setBusy(true); setError(""); setValidation("");
    try {
      const result = await api<ContextPacket>("/api/context/packets", { project, workspace, node: focus, includeNodeIds: neighbors, includeJournalDays, maxBytes });
      if (serial === requestSerial.current && buildScope === currentScope.current) {
        setPacket(result); setDesignContext(selectedDesignContext);
      }
    } catch (e) {
      if (serial === requestSerial.current) setError(String(e));
    } finally { if (serial === requestSerial.current) setBusy(false); }
  }
  function downloadJson() {
    if (!packet || !designContext) return;
    // designContext je lokální návrhový snímek mimo canvasPacket a jeho digest.
    const value = { canvasPacket: packet, designContext, sourceReferences: { project, workspace, paths: selection.references, note: selection.note, contentRead: false } };
    downloadText(`opora-context-${packet.id}.json`, JSON.stringify(value, null, 2), "application/json");
  }
  function downloadMarkdown() {
    if (!packet || !designContext) return;
    downloadText(`opora-context-${packet.id}.md`, packetMarkdown(packet, designContext), "text/markdown;charset=utf-8");
  }
  return <section className="editor-workbench" hidden={!open} aria-label="Nástroje práce s AI">
    <header><strong>Práce s AI · {project}/{workspace}</strong><button onClick={onClose}>Skrýt nástroje</button></header>
    <div className="v3-bench-nav">
      <nav aria-label="AI nástroje"><button className="v3-bench-primary" aria-pressed={pane === "packet"} onClick={() => onPane("packet")}>Podklady pro agenta</button></nav>
      <nav aria-label="Pokročilé nástroje"><span className="v3-tool-label">Pokročilé</span>{([["context", "Kontext"], ["plan", "LLM návrh"], ["coding", "Coding"], ["task", "Dokumentační úkol"]] as const).map(([id, label]) =>
        <button key={id} aria-pressed={pane === id} onClick={() => onPane(id)}>{label}</button>)}</nav>
    </div>
    {pane === "packet" && <div className="workbench-body v3-packet-head"><h2>Podklady pro agenta</h2>
      {packetPanel ? <div className="v3-slot">{packetPanel}</div> : <p>Podklady se sestavují ze skutečně uložených bloků, zadání a vybraných deníků uzlu. Nic se samo neodesílá modelu.</p>}</div>}
    <div hidden={!(pane === "context" || (pane === "packet" && !packetPanel))} className="workbench-body">{pane === "context" && <h2>Kontextový paket</h2>}
      <p>Skutečný snímek uložených bloků, zadání a vybraných deníků. Reference ze shelfu zůstávají pouze lokálními exportními odkazy; jejich obsahy se automaticky nečtou.</p>
      <AgentContextMap graph={graph} focus={focus} packet={packet} designContext={designContext} />
      <label className="field">Uzel paketu<select aria-label="Uzel paketu" value={focus} onChange={(e) => { setFocus(e.target.value); setNeighbors([]); invalidatePacket(); }}><option value="">Vyberte uzel</option>{graph.nodes.map((node) => <option key={node.id} value={node.id}>{node.name}</option>)}</select></label>
      <details><summary>Další uzly a deníky</summary><div className="context-node-options">{graph.nodes.filter((node) => node.id !== focus).map((node) => <label className="check" key={node.id}><input type="checkbox" checked={neighbors.includes(node.id)} disabled={!neighbors.includes(node.id) && neighbors.length >= 20}
        onChange={(e) => { setNeighbors((old) => e.target.checked ? [...old, node.id] : old.filter((id) => id !== node.id)); invalidatePacket(); }} />{node.name}</label>)}</div>
        <label className="field">Dny deníku YYYY-MM-DD, oddělené čárkou<input value={days} onChange={(e) => { setDays(e.target.value); invalidatePacket(); }} /></label></details>
      <label className="field">Limit obsahu paketu (UTF-8 bajty)<input type="number" min={1000} max={500000} value={maxBytes} onChange={(e) => { setMaxBytes(Number(e.target.value)); invalidatePacket(); }} /></label>
      <button className="primary" disabled={busy || !focus || !validMaxBytes} onClick={build}>Sestavit paket</button>
      {error && <p role="alert">{error}</p>}
      {packet && <><p>{packet.sizeBytes} bajtů · vynecháno {packet.excluded.length} · zkráceno {packet.truncated.length}</p><code>{packet.digest}</code>
        <pre data-testid="context-packet-preview">{JSON.stringify(packet.content, null, 2)}</pre>
        <button disabled={busy} onClick={async () => { const serial = ++requestSerial.current; setBusy(true); try { const result = await api<{ stale: boolean }>(`/api/context/packets/${packet.id}/validate`, {}); if (serial === requestSerial.current) setValidation(result.stale ? "Zdroje se změnily — sestavte nový paket." : "Uložené zdroje paketu jsou beze změny."); } catch (e) { if (serial === requestSerial.current) setError(String(e)); } finally { if (serial === requestSerial.current) setBusy(false); } }}>Ověřit aktuálnost</button>
        <button onClick={downloadJson}>Exportovat paket a reference</button><button onClick={downloadMarkdown}>Exportovat paket jako Markdown</button><p data-testid="context-packet-validation">{validation}</p>
      </>}
    </div>
    {visited.has("plan") && <div hidden={pane !== "plan"}><PlanPanel project={project} dirty={false} enabled={open && pane === "plan"} initialWorkspace={workspace} initialLayer={nodeId} /></div>}
    {visited.has("coding") && <div hidden={pane !== "coding"}><CodingPanel project={project} dirty={false} enabled={open && pane === "coding"} initialWorkspace={workspace} initialLayer={nodeId} /></div>}
    {visited.has("task") && <div hidden={pane !== "task"}><TaskHandoffPanel key={JSON.stringify([project, workspace, focus, packet?.id])} project={project} workspace={workspace} nodeId={focus} packetId={packet?.id} enabled={open && pane === "task"} /></div>}
  </section>;
}
