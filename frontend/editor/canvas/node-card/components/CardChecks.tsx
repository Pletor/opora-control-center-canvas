import type { CanvasNode } from "@/shared/types/logic/types";
import type { CompletionEvidence } from "./CardEvidence";

export default function CardChecks({ checks, goal_mode, evidence }: Pick<CanvasNode, "checks" | "goal_mode"> & { evidence?: CompletionEvidence }) {
  if (!checks?.length) return null;
  return <details className="nodrag nopan node-card__fold">
    <summary>{goal_mode === "until_checks_pass" ? "GOAL · " : ""}Kontroly {checks.map(check => {
      const run = evidence?.checksRun.find(item => item.checkId === check.id && item.command === check.command);
      const state = !run ? "wait" : run.exitCode === 0 ? "ok" : "fail";
      const icon = !run ? "…" : run.exitCode === 0 ? "✓" : "✗";
      return <span key={check.id} className={`node-card__chip node-card__chip--${state}`} title={`${check.command}: ${!run ? "bez aktuálního běhu" : `exit ${run.exitCode} · ${run.at}`}`}>{icon} {check.id}</span>;
    })}</summary>
    {checks.map(check => <div key={check.id}><strong>{check.id}</strong> <code>{check.command}</code></div>)}
    {goal_mode === "until_checks_pass" && <p>Pokračovat do úspěchu všech kontrol. Blokaci nebo chybějící oprávnění předat člověku.</p>}
  </details>;
}
