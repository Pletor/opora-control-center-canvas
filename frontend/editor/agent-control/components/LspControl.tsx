import { useRef, useState } from "react";
import type { LspQueryInput, LspQueryResponse, LspStatus } from "@/editor/agent-control/logic/agent-control-api";
import { lspProviderLabel } from "@/editor/agent-control/logic/code-query";

type Props = { disabled: boolean; project: string; workspace: string; status: LspStatus | null; onQuery: (input: LspQueryInput) => Promise<LspQueryResponse> };

/** Keyed by card scope by the parent; request ids reject late answers for a newer question. */
export default function LspControl({ disabled, project, workspace, status, onQuery }: Props) {
  const request = useRef(0);
  const [language, setLanguage] = useState<"typescript" | "python">("typescript");
  const [path, setPath] = useState("");
  const [operation, setOperation] = useState<LspQueryInput["operation"]>("definition");
  const [line, setLine] = useState("0");
  const [character, setCharacter] = useState("0");
  const [result, setResult] = useState<LspQueryResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy || disabled || !path.trim()) return;
    const generation = ++request.current;
    setBusy(true);
    setResult(null);
    setError("");
    try {
      const value = await onQuery({ project, workspace, language, path: path.trim(), operation, line: Number(line), character: Number(character) });
      if (generation === request.current) setResult(value);
    } catch (reason) {
      if (generation === request.current) setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      if (generation === request.current) setBusy(false);
    }
  }

  return <section className="agent-control__lsp" aria-label="Code intelligence">
    <h3 className="agent-control__heading">LSP / code intelligence</h3>
    {status?.providers.map((provider) => <p className="agent-control__meta" key={provider.language}>{provider.language}: <strong>{lspProviderLabel(provider.status)}</strong> · {provider.detail}</p>)}
    {status && <p className="agent-control__warning">Semantic: {status.semantic.status} · {status.semantic.reason}</p>}
    <form className="agent-control__query" onSubmit={(event) => void submit(event)}>
      <select value={language} onChange={(event) => setLanguage(event.target.value as typeof language)} disabled={disabled || busy} aria-label="Jazyk"><option value="typescript">TypeScript</option><option value="python">Python</option></select>
      <input value={path} onChange={(event) => setPath(event.target.value)} disabled={disabled || busy} placeholder="relativní cesta" aria-label="Cesta pro LSP" />
      <select value={operation} onChange={(event) => setOperation(event.target.value as typeof operation)} disabled={disabled || busy} aria-label="LSP operace"><option value="definition">Definition</option><option value="references">References</option><option value="hover">Hover</option><option value="documentSymbols">Document symbols</option></select>
      <input type="number" min="0" value={line} onChange={(event) => setLine(event.target.value)} disabled={disabled || busy} aria-label="Řádek LSP" />
      <input type="number" min="0" value={character} onChange={(event) => setCharacter(event.target.value)} disabled={disabled || busy} aria-label="Znak LSP" />
      <button className="agent-control__button" disabled={disabled || busy || !path.trim()}>{busy ? "Dotazuji…" : "Dotázat LSP"}</button>
    </form>
    {error && <p className="agent-control__error" role="alert">{error}</p>}
    {result && <><p className="agent-control__result">{result.status} · {result.detail} · výsledků: {result.results.length}</p><pre className="agent-control__lsp-results">{JSON.stringify(result.results, null, 2)}</pre></>}
  </section>;
}
