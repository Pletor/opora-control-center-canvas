// Složený oddíl „Předat agentovi“ v záložce Zadání karty: ukáže hotové zadání pro agenta, který kartu
// převezme, a tlačítko, které ho zkopíruje do schránky. Nic neukládá ani nespouští — agenta spouští
// člověk v terminálu se skillem. Zadání skládá čistá funkce `handoffPrompt`; etapu na řadě (`stage`)
// spočítá rodič ze stavu karty. Kopírování a hlášky obstará sdílený `useCopyText`.
import { handoffPrompt, type HandoffStage } from "@/editor/node-detail/handoff/logic/handoff-prompt";
import { COPY_FAILED_TEXT, useCopyText } from "@/shared/hooks/logic/use-copy-text";
import "@/editor/node-detail/handoff/styles/handoff.css";

export default function CardHandoff({
  project,
  workspace,
  nodeId,
  name,
  stage,
}: {
  project: string;
  workspace: string;
  nodeId: string;
  name: string;
  /** Etapa pipeline na řadě, nebo `null`, když karta pipeline nemá nebo je vyřešená. */
  stage: HandoffStage | null;
}) {
  const { status, copy, fieldRef } = useCopyText();
  const prompt = handoffPrompt({ project, workspace, nodeId, name, stage });
  const state = !prompt
    ? "Zadání nejde sestavit: identifikátor projektu, workspace, karty nebo etapy obsahuje nepovolené znaky."
    : stage
      ? `Na řadě je etapa ${stage.title || stage.kind} (${stage.kind}); agent bude hlásit jen ji.`
      : "Zkopírujte zadání a vložte ho agentovi v terminálu se skillem; jeden terminál je jedna karta.";

  return (
    <details className="card-handoff" data-testid="card-handoff">
      <summary className="card-handoff__summary">Předat agentovi</summary>
      <p className="muted card-handoff__state">{state}</p>
      {prompt && (
        <>
          <textarea
            ref={fieldRef}
            className="card-handoff__prompt"
            aria-label="Zadání pro agenta, který převezme kartu"
            data-testid="card-handoff-prompt"
            readOnly
            rows={8}
            value={prompt}
            onFocus={(e) => e.currentTarget.select()}
          />
          <div className="card-handoff__actions">
            <span className="card-handoff__status" role="status">{status === "copied" ? "Zkopírováno" : ""}</span>
            <button type="button" onClick={() => void copy(prompt)} data-testid="card-handoff-copy">
              Kopírovat zadání
            </button>
          </div>
          {status === "failed" && <p className="card-handoff__alert" role="alert">{COPY_FAILED_TEXT}</p>}
        </>
      )}
    </details>
  );
}
