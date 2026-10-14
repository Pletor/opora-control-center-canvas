// Složený oddíl „Rozložit na karty“ v inspektoru sektoru (záložka Zadání): ukáže zadání pro
// agenta-rozkladače sektoru a tlačítko, které ho zkopíruje do schránky. Nic neukládá ani nespouští —
// agenta spouští člověk v terminálu se skillem. Zadání skládá čistá funkce `sectorDecomposePrompt`;
// kopírování a hlášky (úspěch / ruční kopie) obstará sdílený `useCopyText`.
import { czechCount } from "@/editor/canvas/area/logic/area-model";
import { sectorDecomposePrompt } from "@/editor/sector-detail/logic/sector-decompose-prompt";
import { COPY_FAILED_TEXT, useCopyText } from "@/shared/hooks/logic/use-copy-text";
import "@/editor/sector-detail/styles/sector-detail.css";

export default function SectorDecompose({
  project,
  workspace,
  sectorId,
  sectorName,
  purpose,
  cards,
}: {
  project: string;
  workspace: string;
  sectorId: string;
  sectorName: string;
  purpose: string;
  /** Počet karet (`kind: "node"`) přímo v sektoru; spočítá rodič z grafu. */
  cards: number;
}) {
  const { status, copy, fieldRef } = useCopyText();
  const prompt = sectorDecomposePrompt({ project, workspace, sectorId, sectorName, purpose, cards });
  const state = !prompt
    ? "Zadání nejde sestavit: identifikátor projektu, workspace nebo sektoru obsahuje nepovolené znaky."
    : cards > 0
      ? `Sektor má ${czechCount(cards, "kartu", "karty", "karet")}; další rozklad přidá jen nepokrytou část cíle.`
      : "Sektor zatím nemá karty. Zkopírujte zadání a vložte ho agentovi v terminálu se skillem.";

  return (
    <details className="sector-fold" data-testid="sector-decompose">
      <summary className="sector-fold__summary">Rozložit na karty</summary>
      <p className="muted sector-fold__state">{state}</p>
      {prompt && (
        <>
          <textarea
            ref={fieldRef}
            className="sector-fold__prompt"
            aria-label="Zadání pro agenta-rozkladače sektoru"
            data-testid="sector-decompose-prompt"
            readOnly
            rows={10}
            value={prompt}
            onFocus={(e) => e.currentTarget.select()}
          />
          <div className="sector-fold__actions">
            <span className="sector-fold__status" role="status">{status === "copied" ? "Zkopírováno" : ""}</span>
            <button type="button" onClick={() => void copy(prompt)} data-testid="sector-decompose-copy">
              Kopírovat zadání
            </button>
          </div>
          {status === "failed" && <p className="sector-fold__alert" role="alert">{COPY_FAILED_TEXT}</p>}
        </>
      )}
    </details>
  );
}
