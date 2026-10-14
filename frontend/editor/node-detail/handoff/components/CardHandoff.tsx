// Složený oddíl „Předat agentovi“ v záložce Zadání karty: ukáže hotové zadání pro agenta, který kartu
// převezme, a tlačítko, které ho zkopíruje do schránky. Nic neukládá ani nespouští — agenta spouští
// člověk v terminálu se skillem. Zadání skládá čistá funkce `handoffPrompt`; větu o etapě na řadě
// (`stageHint`) spočítá rodič ze stavu karty. Dílek drží jen krátký příznak „Zkopírováno“.
import { useEffect, useState } from "react";
import { handoffPrompt } from "@/editor/node-detail/handoff/logic/handoff-prompt";
import "@/editor/node-detail/handoff/styles/handoff.css";

const COPIED_MS = 2000;

export default function CardHandoff({
  project,
  workspace,
  nodeId,
  name,
  stageHint,
}: {
  project: string;
  workspace: string;
  nodeId: string;
  name: string;
  /** „Na řadě je etapa …“, nebo prázdný řetězec, když karta pipeline nemá. */
  stageHint: string;
}) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), COPIED_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const prompt = handoffPrompt({ project, workspace, nodeId, name, stageHint });
  const copy = () => {
    if (!prompt) return;
    navigator.clipboard.writeText(prompt).then(() => setCopied(true), () => setCopied(false));
  };

  return (
    <details className="card-handoff" data-testid="card-handoff">
      <summary className="card-handoff__summary">Předat agentovi</summary>
      <p className="muted card-handoff__state">
        {stageHint || "Zkopírujte zadání a vložte ho agentovi v terminálu se skillem; jeden terminál je jedna karta."}
      </p>
      {prompt && (
        <>
          <textarea
            className="card-handoff__prompt"
            aria-label="Zadání pro agenta, který převezme kartu"
            data-testid="card-handoff-prompt"
            readOnly
            rows={8}
            value={prompt}
            onFocus={(e) => e.currentTarget.select()}
          />
          <div className="card-handoff__actions">
            <button type="button" onClick={copy} data-testid="card-handoff-copy">
              {copied ? "Zkopírováno" : "Kopírovat zadání"}
            </button>
          </div>
        </>
      )}
    </details>
  );
}
