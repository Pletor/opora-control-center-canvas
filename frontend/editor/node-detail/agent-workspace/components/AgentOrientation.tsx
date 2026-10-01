// Krátký, read-only start pro nového agenta. Všechny karty i hledání vycházejí z právě
// načteného node-briefu; tlačítko jen kopíruje JSON, nikdy samo nevolá model ani neprovádí ACK.
// Brief si dílek nenačítá sám — dostává ho v props od rodiče (AgentWorkspace), který ho drží
// jednou pro celou záložku Agenti; „Načíst znovu“ je jen callback nahoru.
import { useEffect, useMemo, useRef, useState } from "react";
import { orientationSearch, orientationSummary } from "@/editor/node-detail/agent-workspace/logic/agent-orientation";
import type { AgentOrientationFeed } from "@/editor/node-detail/agent-workspace/logic/use-agent-orientation";
import "@/editor/node-detail/agent-workspace/styles/agent-orientation.css";

export default function AgentOrientation({ nodeId, brief, loading, error, reload }: { nodeId: string } & AgentOrientationFeed) {
  const [query, setQuery] = useState(""); const [copied, setCopied] = useState(false); const [clipboardError, setClipboardError] = useState("");
  const timer = useRef<number | null>(null); const summary = useMemo(() => orientationSummary(brief), [brief]); const hits = useMemo(() => orientationSearch(brief, query), [brief, query]);
  const raw = brief as Record<string, unknown> | null; const communication = raw && typeof raw.communication === "object" && raw.communication !== null ? raw.communication as Record<string, unknown> : {};
  const older = (["incoming", "outgoing"] as const).some((direction) => { const page = communication[direction]; return typeof page === "object" && page !== null && (page as Record<string, unknown>).hasMore === true; });
  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current); }, []);

  async function copyBrief() {
    if (!brief || loading || error) return;
    try { await navigator.clipboard.writeText(JSON.stringify(brief, null, 2)); setCopied(true); setClipboardError(""); if (timer.current) window.clearTimeout(timer.current); timer.current = window.setTimeout(() => setCopied(false), 1500); }
    catch { setClipboardError("Schránka není dostupná; JSON nebyl zkopírován."); }
  }

  return <section className="agent-orientation" aria-label="Start pro nového agenta" data-testid="agent-orientation">
    <header className="agent-orientation__head"><div><h3>Start pro nového agenta</h3><p>Jen načtený balíček karty, ne celé úložiště ani historie.</p></div><div className="agent-orientation__actions"><button type="button" className="nodrag" disabled={loading} onClick={reload}>Načíst znovu</button><button type="button" className="nodrag agent-orientation__copy" disabled={!brief || loading || !!error} onClick={() => void copyBrief()}>{copied ? "JSON zkopírován" : "Kopírovat celý JSON"}</button></div></header>
    {loading && <p className="muted">Načítám orientaci…</p>}{error && <p className="agent-orientation__error" role="alert">{error}</p>}{clipboardError && <p className="agent-orientation__error" role="alert">{clipboardError}</p>}
    {!loading && !error && !summary.available && <p className="agent-orientation__error">Orientace v načteném briefu není dostupná; nejde o chybějící cíl.</p>}
    {brief && summary.available && <>
      <p className="agent-orientation__scope">Scope: {summary.path.join(" / ") || nodeId}</p>
      <div className="agent-orientation__cards"><article className="agent-orientation__card"><h4>Cíl</h4><p>{summary.goal || "Chybí — vyžádejte si jej před pokračováním."}</p></article><article className="agent-orientation__card"><h4>Co přečíst</h4><ul>{summary.reading.map((item) => <li key={item.id}>{item.label} <small>· {item.source} · {item.status}</small></li>)}</ul></article><article className="agent-orientation__card"><h4>Co chybí</h4><ul>{summary.gaps.length ? summary.gaps.map((gap) => <li key={gap.id}>{gap.label}: {gap.instruction}</li>) : <li>Balíček nehlásí mezeru.</li>}</ul>{summary.optionalContext.length > 0 && <><h5>Volitelný kontext</h5><ul>{summary.optionalContext.map((item) => <li key={item.id}>{item.label}: {item.instruction}</li>)}</ul></>}</article><article className="agent-orientation__card"><h4>Další krok</h4><p>{summary.nextAction}</p><small>{summary.readOnly ? "Pouze ke čtení; doporučení není právo jednat." : "Doporučení není přijatý úkol ani převod vlastnictví."}</small></article></div>
      <details className="agent-orientation__details"><summary>Definice hotovo a hranice</summary><pre>{JSON.stringify({ definitionOfDone: summary.definitionOfDone, boundaries: summary.boundaries }, null, 2)}</pre></details>
      <label className="agent-orientation__search">Hledat v indexovaném načteném kontextu<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="cíl, pravidlo, blok, podklad nebo zpráva" /></label>{query.trim() && <div className="agent-orientation__results" aria-live="polite">{hits.length ? hits.map((hit) => <p key={hit.id}><strong>{hit.label}</strong><span>{hit.source}</span></p>) : <p>V indexovaném načteném kontextu nebyla shoda.</p>}</div>}
      {older && <p className="agent-orientation__older">Další starší zprávy zůstávají stránkované: otevřete níže Komunikaci mezi agenty a zvolte „Starší zprávy“.</p>}<p className="agent-orientation__safety">Jména agentů nejsou ověřená identita. Tato sekce nic nepotvrzuje, neodesílá ani nepřebírá.</p>
    </>}
  </section>;
}
