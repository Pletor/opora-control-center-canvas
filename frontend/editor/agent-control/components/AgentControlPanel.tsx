import { useEffect, useRef, useState } from "react";
import HookSection from "@/editor/agent-control/components/HookSection";
import LspControl from "@/editor/agent-control/components/LspControl";
import SemanticQuery from "@/editor/agent-control/components/SemanticQuery";
import { fetchLspStatus, queryLsp, type LspStatus } from "@/editor/agent-control/logic/agent-control-api";
import { currentScope, isFreshScope, scopeKey, type Scope } from "@/editor/agent-control/logic/code-query";

type Props = { active: boolean; project: string; workspace: string; selectedNodeId: string | null; readOnly?: boolean };

/** Záložka Kód: LSP a lokální sémantické dohledání nad zdrojem projektu, pod nimi Hook control vybrané karty. Nic nespouští. */
export default function AgentControlPanel({ active, project, workspace, selectedNodeId, readOnly = false }: Props) {
  const scope = currentScope(project, workspace, selectedNodeId);
  const scopeRef = useRef<Scope>(scope);
  const lspTicket = useRef(0);
  scopeRef.current = scope;
  const [lspStatus, setLspStatus] = useState<LspStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const request = ++lspTicket.current;
    setLspStatus(null);
    setError("");
    if (!active) return;
    fetchLspStatus({ project, workspace }).then((value) => {
      if (request === lspTicket.current && isFreshScope(scope, scopeRef.current)) setLspStatus(value);
    }).catch((reason) => {
      if (request === lspTicket.current && isFreshScope(scope, scopeRef.current)) setError(reason instanceof Error ? reason.message : String(reason));
    });
  }, [active, project, workspace, selectedNodeId]);

  return <div className="agent-control" data-testid="agent-control">
    <p className="agent-control__note">Navigace v kódu projektu: nejdřív LSP, sémantika je lokální fallback. Aplikace nic nespouští.</p>
    {error && <p className="agent-control__error" role="alert">{error}</p>}
    <LspControl key={scopeKey("lsp", scope)} disabled={!active} project={project} workspace={workspace} status={lspStatus} onQuery={queryLsp} />
    <SemanticQuery key={scopeKey("semantic", scope)} disabled={!active} project={project} workspace={workspace} />
    <HookSection active={active} project={project} workspace={workspace} selectedNodeId={selectedNodeId} readOnly={readOnly} />
  </div>;
}
