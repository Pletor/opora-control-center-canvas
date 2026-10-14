// Složený oddíl „Rozložit na sektory“ v inspektoru oblasti: z hotového záměru ukáže zadání pro
// agenta-rozkladače a tlačítko, které ho zkopíruje do schránky. Nic neukládá ani nespouští — agenta
// spouští člověk v terminálu se skillem. Zadání skládá čistá funkce `decomposePrompt`; kopírování a
// hlášky (úspěch / ruční kopie) obstará sdílený `useCopyText`.
import { czechCount } from "@/editor/canvas/area/logic/area-model";
import { decomposePrompt } from "@/editor/canvas/area/logic/decompose-prompt";
import { COPY_FAILED_TEXT, useCopyText } from "@/shared/hooks/logic/use-copy-text";
import "@/editor/canvas/area/styles/area.css";

export default function AreaDecompose({
  project,
  workspace,
  areaId,
  areaName,
  intent,
  sectors,
}: {
  project: string;
  workspace: string;
  areaId: string;
  areaName: string;
  /** Záměr tak, jak je uložený (`node.purpose`); rozepsaný text se sem dostane až po uložení. */
  intent: string;
  sectors: number;
}) {
  const { status, copy, fieldRef } = useCopyText();
  const prompt = decomposePrompt({ project, workspace, areaId, areaName, intent, sectors });
  const state = !intent.trim()
    ? "Nejdřív napište záměr."
    : !prompt
      ? "Zadání nejde sestavit: identifikátor projektu, workspace nebo oblasti obsahuje nepovolené znaky."
      : sectors > 0
        ? `Oblast má ${czechCount(sectors, "sektor", "sektory", "sektorů")}; další rozklad přidá nové vedle nich.`
        : "Zkopírujte zadání a vložte ho agentovi v terminálu se skillem.";

  return (
    <details className="area-decompose" data-testid="area-decompose">
      <summary className="area-decompose__summary">Rozložit na sektory</summary>
      <p className="muted area-decompose__state">{state}</p>
      {prompt && (
        <>
          <textarea
            ref={fieldRef}
            className="area-decompose__prompt"
            aria-label="Zadání pro agenta-rozkladače"
            data-testid="area-decompose-prompt"
            readOnly
            rows={10}
            value={prompt}
            onFocus={(e) => e.currentTarget.select()}
          />
          <div className="area-decompose__actions">
            <span className="area-decompose__status" role="status">{status === "copied" ? "Zkopírováno" : ""}</span>
            <button type="button" onClick={() => void copy(prompt)} data-testid="area-decompose-copy">
              Kopírovat zadání
            </button>
          </div>
          {status === "failed" && <p className="area-decompose__alert" role="alert">{COPY_FAILED_TEXT}</p>}
        </>
      )}
    </details>
  );
}
