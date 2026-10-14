// Blok „Vybraná karta“ v sekci Struktura: co agent vybrané karty dostane. Stáhne balíček pro model
// (`GET /api/desktop-v3/node-brief`), složí z něj pohled a vykreslí ho jen ke čtení — hlavičku,
// pět sekcí a dvě tlačítka na zkopírování. Aplikace tím žádný model nespouští: zadání je data,
// která si člověk odnese do schránky. Zápis sem nepatří; upravuje se v inspektoru karty.
import { useState } from "react";
import CardBriefHeader from "@/layout/card-brief/components/CardBriefHeader";
import CardBriefSections from "@/layout/card-brief/components/CardBriefSections";
import { briefJson, briefSummary, handoffLink } from "@/layout/card-brief/logic/card-brief-view";
import { useNodeBrief } from "@/layout/card-brief/logic/use-node-brief";
import "@/layout/card-brief/styles/card-brief.css";

/** Co se naposledy povedlo zkopírovat; prohlížeč smí schránku odmítnout, a to se má říct. */
type Copied = "" | "brief" | "link" | "blocked";

export default function CardBrief({
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
      <div className="card-brief__agents" data-testid="card-brief-agents">
        <p className="card-brief__note">Vyberte kartu.</p>
        <p className="card-brief__note card-brief__note--quiet">
          Tady se ukáže, co agent té karty dostane: cíl, kritéria konce, harness, smyčka a předávky sousedů.
        </p>
      </div>
    );
  }

  const summary = brief ? briefSummary(brief) : null;
  return (
    <div className="card-brief__agents" data-testid="card-brief-agents">
      {loading && !summary && <p className="card-brief__note">Načítám zadání karty…</p>}
      {error && (
        <p className="card-brief__note card-brief__note--error" data-testid="card-brief-brief-error">
          {error}
        </p>
      )}
      {summary && (
        <div className="card-brief__brief" data-testid="card-brief-brief">
          <CardBriefHeader header={summary.header} />
          <CardBriefSections summary={summary} />
          <div className="card-brief__brief-actions">
            <button
              type="button"
              className="card-brief__brief-button card-brief__brief-button--main"
              data-testid="card-brief-copy-brief"
              onClick={() => void copy("brief", briefJson(brief))}
            >
              {copied === "brief" ? "Zkopírováno" : "Kopírovat zadání pro agenta"}
            </button>
            <button
              type="button"
              className="card-brief__brief-button"
              data-testid="card-brief-copy-link"
              onClick={() => void copy("link", handoffLink(selectedNodeId))}
            >
              {copied === "link" ? "Zkopírováno" : "Kopírovat odkaz"}
            </button>
          </div>
          {copied === "blocked" && (
            <p className="card-brief__note card-brief__note--error">Kopírování odmítl prohlížeč.</p>
          )}
        </div>
      )}
    </div>
  );
}
