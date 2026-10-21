import type { AgentAction, AgentGap } from "@/hub/oporahub-agent-state/logic/agent-state";
import type { BudgetContext } from "@/hub/execution-budgets/logic/execution-budgets";
import type { ExecutionSummary } from "@/hub/execution-receipts/logic/execution-receipts";
import type { PlanChangeset } from "@/hub/plan-changes/logic/plan-changes";
import { ToneChip } from "@/hub/oporahub-health/components/HealthMark";

function Gauge({ label, used, max, unit = "" }: { label: string; used: number | null; max: number | null; unit?: string }) {
  const known = used !== null && max !== null && max > 0, pct = known ? Math.min(100, Math.round(used / max * 100)) : 0;
  return <div className="oporahub-card__gauge-row">
    <span>{label}</span>
    <span className="oporahub-card__gauge" role="meter" aria-valuemin={0} aria-valuemax={max ?? 0} aria-valuenow={used ?? 0} aria-label={label}>
      <i className={pct >= 90 ? "oporahub-card__gauge-fill oporahub-card__gauge-fill--bad" : pct >= 60 ? "oporahub-card__gauge-fill oporahub-card__gauge-fill--warn" : "oporahub-card__gauge-fill"} style={{ width: `${pct}%` }} />
    </span>
    <b className="oporahub-card__mono">{known ? `${used} / ${max}${unit}` : "neznámé"}</b>
  </div>;
}

/** Lease a rozpočet: kolik pokusů, oprav a času zbývá; heartbeat neprodlužuje pevný konec běhu. */
export function CardBudget({ budget, latest, claim }: { budget: BudgetContext | null; latest: ExecutionSummary | null; claim: AgentAction | null }) {
  const limits = budget?.policy?.limits ?? null;
  const left = latest?.state === "running" && Number.isFinite(latest.expiresAt - latest.serverNow) ? Math.max(0, Math.round(latest.expiresAt - latest.serverNow)) : null;
  return <section className="oporahub-card__panel" data-oh-field="lease">
    <header className="oporahub-card__panel-head"><h2 className="oporahub-card__title">Lease a rozpočet</h2>
      <span className="oporahub-card__note">{latest ? `${latest.executionId.slice(0, 8)} · epocha ${latest.epoch}` : "bez běhu"}</span></header>
    <div className="oporahub-card__body">
      <Gauge label="Pokusy" used={budget?.attemptsUsed ?? null} max={limits?.maxAttempts ?? null} />
      <Gauge label="Opravy" used={budget?.repairRoundsUsed ?? null} max={limits?.maxRepairRounds ?? null} />
      <Gauge label="Čas běhu" used={latest?.budget && left !== null ? Math.max(0, latest.budget.maxRunSeconds - left) : null} max={latest?.budget?.maxRunSeconds ?? null} unit=" s" />
      {claim?.budget && <span className="oporahub-card__note">Agent-state: zbývá {claim.budget.remainingAttempts ?? "?"} pokusů a {claim.budget.remainingRepairRounds ?? "?"} oprav.</span>}
      {!budget?.enrolled && <span className="oporahub-card__note">Karta nemá nastavená pravidla běhů (protokol v1).</span>}
      <span className="oporahub-card__note">Heartbeat neprodlužuje pevný konec běhu. Zrušení člověkem pokus nevrací.</span>
    </div>
  </section>;
}

/** Přijetí vázaná na revizi: přijatá změna platí jen pro rodiče, ze kterého vznikla. */
export function CardApprovals({ changesets }: { changesets: PlanChangeset[] }) {
  return <section className="oporahub-card__panel">
    <header className="oporahub-card__panel-head"><h2 className="oporahub-card__title">Přijetí vázaná na revizi</h2><span className="oporahub-card__note">jiná revize = neplatné</span></header>
    <div className="oporahub-card__table" role="table">
      {changesets.filter(item => item.accepted).map(item => <div key={item.id} role="row" className="oporahub-card__table-row" data-oh-changeset={item.id} data-oh-accepted="true">
        <span role="cell">Přijetí {item.id.slice(0, 10)}</span><span role="cell">{item.by.name}</span>
        <code role="cell" className="oporahub-card__mono">{item.parentRevision.slice(0, 12)}</code><span role="cell"><ToneChip tone="ok">✓ přijato</ToneChip></span>
      </div>)}
      {!changesets.some(item => item.accepted) && <p className="oporahub-card__note oporahub-card__body">Karta zatím nemá přijatou změnu zadání v načtené historii.</p>}
    </div>
  </section>;
}

/** Druhy důkazů: co je doloženo a co ještě není napojené (Lean, AI review). */
export function CardEvidence({ latest, gaps }: { latest: ExecutionSummary | null; gaps: AgentGap[] }) {
  return <section className="oporahub-card__panel">
    <header className="oporahub-card__panel-head"><h2 className="oporahub-card__title">Důkazy</h2><span className="oporahub-card__note">model není důkaz implementace</span></header>
    <div className="oporahub-card__body">
      <span className="oporahub-card__evidence">{latest?.state === "reported" ? <ToneChip tone="warn">◷ Výsledek nahlášen, neověřen</ToneChip> : <ToneChip tone="gap">◌ Bez nahlášeného výsledku</ToneChip>}</span>
      {gaps.filter(item => item.stage === "evidence" || item.stage === "review").map(item =>
        <span key={item.id} className="oporahub-card__evidence" data-oh-gap={item.id}><ToneChip tone="gap">◌ zatím nenapojeno</ToneChip>{item.reason}</span>)}
    </div>
  </section>;
}
