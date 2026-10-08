import { useMemo, useState } from "react";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import { buildDnaExport } from "../logic/dna-export";
import { useDnaHistory } from "../logic/use-dna-history";

type Props = { node: CanvasNode; data: NodeCardData; state: DesktopState; graph: Graph; project?: string; workspace?: string };

/** DNA exportuje jen skutečně načtené podklady a chybu schránky oznamuje přímo člověku. */
export default function CardDnaExport({ node, data, state, graph, project, workspace }: Props) {
  const history = useDnaHistory(project, workspace, node.id); const [copied, setCopied] = useState(false); const [clipboardError, setClipboardError] = useState("");
  const markdown = useMemo(() => buildDnaExport({ node, data, state, graph, brief: history.brief, results: history.results, messages: history.messages, partialHistory: history.partial }), [data, graph, history.brief, history.partial, history.results, history.messages, node, state]);
  const sourceReady = !!history.brief && !history.loading && !history.error;
  const copy = async () => { if (!sourceReady) return; try { await navigator.clipboard.writeText(markdown); setCopied(true); setClipboardError(""); } catch (reason) { setCopied(false); setClipboardError(reason instanceof Error ? reason.message : String(reason)); } };
  return <section className="card-dna__export-panel">
    <header><h3>DNA karty</h3><button type="button" disabled={!sourceReady} onClick={() => void copy()}>{copied ? "DNA zkopírována" : "Kopírovat DNA karty"}</button></header>
    {history.loading && <p role="status">Načítám node-brief a první stránky historie…</p>}
    {history.error && <p role="alert">{history.error}</p>}
    {clipboardError && <p role="alert">Kopírování selhalo: {clipboardError}</p>}
    {history.partial && <p className="card-dna__partial">Export obsahuje načtené stránky, ne úplnou historii.</p>}
    {history.partial && <p><button type="button" disabled={history.loadingMore} onClick={() => void history.loadMore()}>{history.loadingMore ? "Načítám…" : "Načíst další stránky"}</button> <button type="button" disabled={history.loadingMore} onClick={() => void history.loadAll()}>Načíst vše pro export</button></p>}
    <pre className="card-dna__export">{markdown}</pre>
  </section>;
}
