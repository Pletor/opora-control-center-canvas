import { useEffect, useState } from "react";
import { planBuildLines, type PlanBuild } from "../logic/plan-build";
import "../styles/plan-build.css";

type Props = {
  pageId: string; domainId: string;
  /** Stavba pro stránku nebo doménu (`id`); síť drží rodič (`buildPlan`). */
  onBuild: (id: string) => Promise<PlanBuild>;
  /** Plátno 3 (Editor) nad procesem stránky, jinak nad doménou. */
  onOpenEditor: (id: string) => void;
};
type State = { phase: "idle" | "busy" } | { phase: "done"; build: PlanBuild } | { phase: "failed"; error: string };

/** „Postavit plán práce“ v hlavičce plátna 2: srdce navrhne plátno 3 ze stránky (nebo celé domény), panel řekne výsledek. */
export default function PlanBuildButton({ pageId, domainId, onBuild, onOpenEditor }: Props) {
  const [state, setState] = useState<State>({ phase: "idle" });
  useEffect(() => setState({ phase: "idle" }), [pageId]);
  const run = (id: string) => {
    setState({ phase: "busy" });
    onBuild(id).then((build) => setState({ phase: "done", build }),
      (cause) => setState({ phase: "failed", error: cause instanceof Error ? cause.message : String(cause) }));
  };
  return <div className="plan-build">
    <button type="button" className="plan-build__run" disabled={state.phase === "busy"} data-testid="architecture-build-plan"
      onClick={() => run(pageId)}>{state.phase === "busy" ? "Srdce staví…" : "▦ Postavit plán práce"}</button>
    {(state.phase === "done" || state.phase === "failed") && <div className="plan-build__panel" role="status" data-testid="architecture-build-plan-result">
      {state.phase === "failed" ? <p className="plan-build__line plan-build__line--error">{state.error}</p>
        : planBuildLines(state.build).map((line) => <p key={line} className="plan-build__line">{line}</p>)}
      <div className="plan-build__actions">
        <button type="button" onClick={() => onOpenEditor(state.phase === "done" ? state.build.frameId ?? domainId : domainId)}>Otevřít v Editoru →</button>
        <button type="button" onClick={() => run(domainId)}>Celá doména</button>
        <button type="button" className="plan-build__close" aria-label="Zavřít" onClick={() => setState({ phase: "idle" })}>✕</button>
      </div>
    </div>}
  </div>;
}
