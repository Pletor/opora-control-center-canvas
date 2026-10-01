import { useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";

type SemanticStatus = { status: "configured" | "unavailable"; model: string; detail: string; localOnly: true };
type SemanticResult = { path: string; startLine: number; endLine: number; snippet: string; score: number };
type SemanticResponse = { status: "ok" | "empty" | "unavailable"; results: SemanticResult[]; model: string; localOnly: true; filesScanned: number; chunksIndexed: number; truncated: boolean; detail: string };
type Props = { disabled: boolean; project: string; workspace: string };

/** Keyed by scope by the parent; request ids also discard out-of-order answers within a scope. */
export default function SemanticQuery({ disabled, project, workspace }: Props) {
  const request = useRef(0);
  const [path, setPath] = useState("");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState("8");
  const [status, setStatus] = useState<SemanticStatus | null>(null);
  const [result, setResult] = useState<SemanticResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function checkStatus() {
    if (busy || disabled) return;
    const generation = ++request.current;
    setBusy(true);
    setStatus(null);
    setResult(null);
    setError("");
    try {
      const value = await api<SemanticStatus>(`/api/semantic-search/status?${new URLSearchParams({ project, workspace })}`);
      if (generation === request.current) setStatus(value);
    } catch (reason) {
      if (generation === request.current) setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      if (generation === request.current) setBusy(false);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy || disabled || !path.trim() || !query.trim()) return;
    const generation = ++request.current;
    setBusy(true);
    // A new question must never be presented with the previous answer or error.
    setResult(null);
    setError("");
    try {
      const value = await api<SemanticResponse>("/api/semantic-search/query", { project, workspace, path: path.trim(), query: query.trim(), limit: Number(limit) });
      if (generation === request.current) setResult(value);
    } catch (reason) {
      if (generation === request.current) setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      if (generation === request.current) setBusy(false);
    }
  }

  return <section className="agent-control__semantic" aria-label="Sémantické dohledání">
    <h3 className="agent-control__heading">Sémantické dohledání (fallback po LSP)</h3>
    <button type="button" className="agent-control__button" disabled={disabled || busy} onClick={() => void checkStatus()}>{busy ? "Zjišťuji…" : "Zjistit stav modelu"}</button>
    {status && <p className={status.status === "unavailable" ? "agent-control__warning" : "agent-control__meta"}>{status.status} · {status.model} · {status.detail} · pouze lokálně</p>}
    <form className="agent-control__query" onSubmit={(event) => void submit(event)}>
      <input value={path} onChange={(event) => setPath(event.target.value)} disabled={disabled || busy} placeholder="relativní podstrom nebo soubor" aria-label="Rozsah sémantického hledání" />
      <input value={query} onChange={(event) => setQuery(event.target.value)} disabled={disabled || busy} placeholder="co hledat" aria-label="Sémantický dotaz" />
      <input type="number" min="1" max="128" value={limit} onChange={(event) => setLimit(event.target.value)} disabled={disabled || busy} aria-label="Limit sémantických výsledků" />
      <button className="agent-control__button" disabled={disabled || busy || !path.trim() || !query.trim()}>{busy ? "Hledám…" : "Hledat lokálně"}</button>
    </form>
    {error && <p className="agent-control__error" role="alert">{error}</p>}
    {result && <div className="agent-control__semantic-results"><p className={result.status === "unavailable" ? "agent-control__warning" : "agent-control__result"}>{result.status} · {result.detail} · soubory {result.filesScanned}, chunky {result.chunksIndexed}{result.truncated ? " · výstup zkrácen" : ""}</p>{result.results.map((item) => <p className="agent-control__event" key={`${item.path}:${item.startLine}`}>{item.path}:{item.startLine}–{item.endLine} · podobnost {item.score} · {item.snippet}</p>)}</div>}
  </section>;
}
