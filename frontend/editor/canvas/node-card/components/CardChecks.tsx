import type { CanvasNode } from "@/shared/types/logic/types";
import type { CompletionEvidence } from "./CardEvidence";

export default function CardChecks({ checks, goal_mode, evidence }: Pick<CanvasNode, "checks" | "goal_mode"> & { evidence?: CompletionEvidence }) {
  if (!checks?.length) return null;
  return <details className="nodrag nopan" style={{ padding: "6px 12px" }}>
    <summary>{goal_mode === "until_checks_pass" ? "GOAL · " : ""}Kontroly {checks.map(check => {
      const run = evidence?.checksRun.find(item => item.checkId === check.id && item.command === check.command);
      const icon = !run ? "…" : run.exitCode === 0 ? "✓" : "✗";
      return <span key={check.id} title={`${check.command}: ${!run ? "bez aktuálního běhu" : `exit ${run.exitCode} · ${run.at}`}`} style={{ marginLeft: 6, color: !run ? "inherit" : run.exitCode === 0 ? "#22c55e" : "#ef4444" }}>{icon} {check.id}</span>;
    })}</summary>
    {checks.map(check => <div key={check.id}><strong>{check.id}</strong> <code>{check.command}</code></div>)}
    {goal_mode === "until_checks_pass" && <p>Pokračovat do úspěchu všech kontrol. Blokaci nebo chybějící oprávnění předat člověku.</p>}
  </details>;
}
