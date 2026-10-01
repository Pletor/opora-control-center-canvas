// Záložka Agenti: co agent vybrané karty dostane. Stáhne balíček pro model
// (`GET /api/desktop-v3/node-brief`), složí z něj pohled a vykreslí ho jen ke čtení — hlavičku,
// pět sekcí a dvě tlačítka na zkopírování. Aplikace tím žádný model nespouští: zadání je data,
// která si člověk odnese do schránky. Zápis sem nepatří; upravuje se v inspektoru karty.
import { useState } from "react";
import AgentBriefHeader from "@/layout/agent-navbar/components/AgentBriefHeader";
import AgentBriefSections from "@/layout/agent-navbar/components/AgentBriefSections";
import { briefJson, briefSummary, handoffLink } from "@/layout/agent-navbar/logic/agent-brief-view";
import { useNodeBrief } from "@/layout/agent-navbar/logic/use-node-brief";

/** Co se naposledy povedlo zkopírovat; prohlížeč smí schránku odmítnout, a to se má říct. */
type Copied = "" | "brief" | "link" | "blocked";

export default function AgentNavbarAgents({
  project,
  workspace,
  selectedNodeId,
  refreshKey,
}: {
  project: string;
  workspace: string;
  /** Karta, na kterou se panel ptá; sám si ji nikdy nedohledává. */
  selectedNodeId: string | null;
  /** Otisk plátna a revize plochy: změní se, když se karta pod panelem pohne, a zadání se načte znovu. */
  refreshKey: string;
}) {
  const { brief, loading, error } = useNodeBrief(project, workspace, selectedNodeId, refreshKey);
  const [copied, setCopied] = useState<Copied>("");

  async function copy(what: Copied, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
    } catch {
      setCopied("blocked");
    }
  }

  if (!selectedNodeId) {
    return (
      <div className="agent-navbar__agents" data-testid="agent-navbar-agents">
        <p className="agent-navbar__note">Vyberte kartu.</p>
        <p className="agent-navbar__note agent-navbar__note--quiet">
          Tady se ukáže, co agent té karty dostane: cíl, kritéria konce, harness, smyčka a předávky sousedů.
        </p>
      </div>
    );
  }

  const summary = brief ? briefSummary(brief) : null;
  return (
    <div className="agent-navbar__agents" data-testid="agent-navbar-agents">
      {loading && !summary && <p className="agent-navbar__note">Načítám zadání karty…</p>}
      {error && (
        <p className="agent-navbar__note agent-navbar__note--error" data-testid="agent-navbar-brief-error">
          {error}
        </p>
      )}
      {summary && (
        <div className="agent-navbar__brief" data-testid="agent-navbar-brief">
          <AgentBriefHeader header={summary.header} />
          <AgentBriefSections summary={summary} />
          <div className="agent-navbar__brief-actions">
            <button
              type="button"
              className="agent-navbar__brief-button agent-navbar__brief-button--main"
              data-testid="agent-navbar-copy-brief"
              onClick={() => void copy("brief", briefJson(brief))}
            >
              {copied === "brief" ? "Zkopírováno" : "Kopírovat zadání pro agenta"}
            </button>
            <button
              type="button"
              className="agent-navbar__brief-button"
              data-testid="agent-navbar-copy-link"
              onClick={() => void copy("link", handoffLink(selectedNodeId))}
            >
              {copied === "link" ? "Zkopírováno" : "Kopírovat odkaz"}
            </button>
          </div>
          {copied === "blocked" && (
            <p className="agent-navbar__note agent-navbar__note--error">Kopírování odmítl prohlížeč.</p>
          )}
        </div>
      )}
    </div>
  );
}
