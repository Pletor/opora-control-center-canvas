// Složený oddíl „Rozložit na sektory“ v inspektoru oblasti: z hotového záměru ukáže zadání pro
// agenta-rozkladače a tlačítko, které ho zkopíruje do schránky. Nic neukládá ani nespouští — agenta
// spouští člověk v terminálu se skillem. Zadání skládá čistá funkce `decomposePrompt`; dílek drží jen
// krátký příznak „Zkopírováno“.
import { useEffect, useState } from "react";
import { czechCount } from "@/editor/canvas/area/logic/area-model";
import { decomposePrompt } from "@/editor/canvas/area/logic/decompose-prompt";
import "@/editor/canvas/area/styles/area.css";

const COPIED_MS = 2000;

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
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), COPIED_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const prompt = decomposePrompt({ project, workspace, areaId, areaName, intent, sectors });
  const state = !prompt
    ? "Nejdřív napište záměr."
    : sectors > 0
      ? `Oblast má ${czechCount(sectors, "sektor", "sektory", "sektorů")}; další rozklad přidá nové vedle nich.`
      : "Zkopírujte zadání a vložte ho agentovi v terminálu se skillem.";

  const copy = () => {
    if (!prompt) return;
    navigator.clipboard.writeText(prompt).then(() => setCopied(true), () => setCopied(false));
  };

  return (
    <details className="area-decompose" data-testid="area-decompose">
      <summary className="area-decompose__summary">Rozložit na sektory</summary>
      <p className="muted area-decompose__state">{state}</p>
      {prompt && (
        <>
          <textarea
            className="area-decompose__prompt"
            aria-label="Zadání pro agenta-rozkladače"
            data-testid="area-decompose-prompt"
            readOnly
            rows={10}
            value={prompt}
            onFocus={(e) => e.currentTarget.select()}
          />
          <div className="area-decompose__actions">
            <button type="button" onClick={copy} data-testid="area-decompose-copy">
              {copied ? "Zkopírováno" : "Kopírovat zadání"}
            </button>
          </div>
        </>
      )}
    </details>
  );
}
