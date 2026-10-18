// Složený oddíl „Shrnout podněty (N)“ v inspektoru sektoru: místo seznamu podnětů k proklikání ukáže
// zadání pro agenta, který je shrne do jednoho rozhodnutí, a tlačítko na zkopírování. Rodič (NodePanel)
// ho montuje jen pro sektor s otevřenými podněty v kartách; počet spočítá App. Nic neukládá ani
// nespouští; kopírování a hlášky obstará sdílený `useCopyText`.
import { ideasSummaryPrompt } from "@/editor/sector-detail/logic/ideas-summary-prompt";
import { COPY_FAILED_TEXT, useCopyText } from "@/shared/hooks/logic/use-copy-text";
import "@/editor/sector-detail/styles/sector-detail.css";

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
  const { status, copy, fieldRef } = useCopyText();
  const prompt = ideasSummaryPrompt({ project, workspace, sectorId, sectorName, openIdeas });
  if (!prompt) return null;

  return (
    <details className="sector-fold" data-testid="ideas-summary">
      <summary className="sector-fold__summary">Shrnout podněty ({openIdeas})</summary>
      <p className="muted sector-fold__state">
        Podněty agentů z karet sektoru shrne agent do nejvýš tří témat a jednoho rozhodnutí pro vás.
      </p>
      <textarea
        ref={fieldRef}
        className="sector-fold__prompt"
        aria-label="Zadání pro shrnutí podnětů sektoru"
        data-testid="ideas-summary-prompt"
        readOnly
        rows={8}
        value={prompt}
        onFocus={(e) => e.currentTarget.select()}
      />
      <div className="sector-fold__actions">
        <span className="sector-fold__status" role="status">{status === "copied" ? "Zkopírováno" : ""}</span>
        <button type="button" onClick={() => void copy(prompt)} data-testid="ideas-summary-copy">
          Kopírovat zadání
        </button>
      </div>
      {status === "failed" && <p className="sector-fold__alert" role="alert">{COPY_FAILED_TEXT}</p>}
    </details>
  );
}
