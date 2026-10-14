// Složený oddíl „Shrnout podněty (N)“ v inspektoru sektoru: místo seznamu podnětů k proklikání ukáže
// zadání pro agenta, který je shrne do jednoho rozhodnutí, a tlačítko na zkopírování. Rodič (NodePanel)
// ho montuje jen pro sektor s otevřenými podněty v kartách; počet spočítá App. Nic neukládá ani
// nespouští, drží jen krátký příznak „Zkopírováno“.
import { useEffect, useState } from "react";
import { ideasSummaryPrompt } from "@/editor/sector-detail/logic/ideas-summary-prompt";
import "@/editor/sector-detail/styles/sector-detail.css";

const COPIED_MS = 2000;

export default function IdeasSummary({
  project,
  workspace,
  sectorId,
  sectorName,
  openIdeas,
}: {
  project: string;
  workspace: string;
  sectorId: string;
  sectorName: string;
  /** Otevřené podněty ve všech kartách sektoru. */
  openIdeas: number;
}) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), COPIED_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const prompt = ideasSummaryPrompt({ project, workspace, sectorId, sectorName, openIdeas });
  if (!prompt) return null;
  const copy = () => {
    navigator.clipboard.writeText(prompt).then(() => setCopied(true), () => setCopied(false));
  };

  return (
    <details className="sector-fold" data-testid="ideas-summary">
      <summary className="sector-fold__summary">Shrnout podněty ({openIdeas})</summary>
      <p className="muted sector-fold__state">
        Podněty agentů z karet sektoru shrne agent do nejvýš tří témat a jednoho rozhodnutí pro vás.
      </p>
      <textarea
        className="sector-fold__prompt"
        aria-label="Zadání pro shrnutí podnětů sektoru"
        data-testid="ideas-summary-prompt"
        readOnly
        rows={8}
        value={prompt}
        onFocus={(e) => e.currentTarget.select()}
      />
      <div className="sector-fold__actions">
        <button type="button" onClick={copy} data-testid="ideas-summary-copy">
          {copied ? "Zkopírováno" : "Kopírovat zadání"}
        </button>
      </div>
    </details>
  );
}
