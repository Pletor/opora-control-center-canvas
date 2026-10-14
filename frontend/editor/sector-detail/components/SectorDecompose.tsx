// Složený oddíl „Rozložit na karty“ v inspektoru sektoru (záložka Zadání): ukáže zadání pro
// agenta-rozkladače sektoru a tlačítko, které ho zkopíruje do schránky. Nic neukládá ani nespouští —
// agenta spouští člověk v terminálu se skillem. Zadání skládá čistá funkce `sectorDecomposePrompt`;
// dílek drží jen krátký příznak „Zkopírováno“.
import { useEffect, useState } from "react";
import { czechCount } from "@/editor/canvas/area/logic/area-model";
import { sectorDecomposePrompt } from "@/editor/sector-detail/logic/sector-decompose-prompt";
import "@/editor/sector-detail/styles/sector-detail.css";

const COPIED_MS = 2000;

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
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), COPIED_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const prompt = sectorDecomposePrompt({ project, workspace, sectorId, sectorName, purpose, cards });
  const state = cards > 0
    ? `Sektor má ${czechCount(cards, "kartu", "karty", "karet")}; další rozklad přidá jen nepokrytou část cíle.`
    : "Sektor zatím nemá karty. Zkopírujte zadání a vložte ho agentovi v terminálu se skillem.";

  const copy = () => {
    if (!prompt) return;
    navigator.clipboard.writeText(prompt).then(() => setCopied(true), () => setCopied(false));
  };

  return (
    <details className="sector-fold" data-testid="sector-decompose">
      <summary className="sector-fold__summary">Rozložit na karty</summary>
      <p className="muted sector-fold__state">{state}</p>
      {prompt && (
        <>
          <textarea
            className="sector-fold__prompt"
            aria-label="Zadání pro agenta-rozkladače sektoru"
            data-testid="sector-decompose-prompt"
            readOnly
            rows={10}
            value={prompt}
            onFocus={(e) => e.currentTarget.select()}
          />
          <div className="sector-fold__actions">
            <button type="button" onClick={copy} data-testid="sector-decompose-copy">
              {copied ? "Zkopírováno" : "Kopírovat zadání"}
            </button>
          </div>
        </>
      )}
    </details>
  );
}
