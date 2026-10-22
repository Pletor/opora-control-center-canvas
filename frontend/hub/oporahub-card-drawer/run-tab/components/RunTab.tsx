import { useNow } from "@/editor/node-detail/agent-summary/logic/use-now";
import AgentWorkspace from "@/editor/node-detail/agent-workspace/components/AgentWorkspace";
import { unixTime } from "@/hub/execution-receipts/logic/execution-receipts";
import type { CardData } from "../../logic/use-card-data";
import type { DrawerEditor } from "../../logic/drawer-editor";
import { budgetMeters, leaseView, selfCheckChips } from "../logic/run-view";
import "../styles/run-tab.css";

type Props = { project: string; workspace: string; nodeId: string; data: CardData; editor: DrawerEditor | null; onWorkspace: () => void };
const CHECK_GLYPH = { ok: "✓", failed: "✕", missing: "◷" } as const;

/** Záložka Běh: lease s odpočtem, neměnný snímek zadání, rozpočet, výsledky kroků a samokontroly agenta. */
export default function RunTab({ project, workspace, nodeId, data, editor, onWorkspace }: Props) {
  const now = useNow(1000).getTime() / 1000;
  const run = data.latest, lease = leaseView(run, now, data.loadedAt);
  const meters = budgetMeters(data.budget, run, run ? run.serverNow + Math.max(0, now - data.loadedAt) : null);
  const checks = selfCheckChips(data.gate?.mergeReadiness.selfChecks, data.gate?.mergeReadiness.requiredChecks);
  const results = [...data.stepResults.values()].sort((a, b) => a.stepId.localeCompare(b.stepId, "cs", { numeric: true }));
  const assigned = editor?.workspaces.filter(item => item.node_id === nodeId) ?? [];
  return <div className="run-tab" data-oh-view="card-run" data-oh-execution={run?.executionId ?? ""} data-oh-epoch={run?.epoch ?? ""}
    data-oh-execution-state={run?.state ?? "none"} data-oh-lease-state={lease.state} data-oh-lease-remaining={Math.round(lease.remaining)}>
    <section className={`run-tab__lease run-tab__lease--${lease.state}`} aria-label="Lease běhu">
      <span className="run-tab__label">Lease · {lease.state === "active" ? "zbývá" : lease.state === "expired" ? "vypršela" : "bez aktivní lease"}</span>
      <b className="run-tab__clock" data-oh-field="lease-countdown" data-oh-value={lease.label}>{lease.label}</b>
      <span className="run-tab__track"><i style={{ width: `${Math.round(lease.fraction * 100)}%` }} /></span>
      <span className="run-tab__muted">{lease.text}</span>
    </section>
    {run ? <dl className="run-tab__facts">
      <dt>Exekuce</dt><dd><code>{run.executionId.slice(0, 12)}</code> · {run.createdAt ? run.createdAt.slice(0, 16).replace("T", " ") : unixTime(run.serverNow)}</dd>
      <dt>Agent</dt><dd data-oh-field="lease-holder" data-oh-value={run.owner ?? ""}>{run.owner ?? "neznámý"} · epocha {run.epoch}</dd>
      <dt>Zadání</dt><dd data-oh-field="assignment" data-oh-value={run.assignmentDigest}>snímek {run.acceptedRevision.slice(0, 8)} · <code>{run.assignmentDigest.slice(0, 12)}</code></dd>
      {run.budget && <><dt>Pokus</dt><dd>{run.budget.kind} · pokus {run.budget.attempt} · oprava {run.budget.repairRound}</dd></>}
    </dl> : data.agent?.actions.some(item => item.verb === "claim" && item.targetId === nodeId) ? <p className="run-tab__muted" data-oh-claim-ready="true">Karta je připravená k převzetí.</p> : null}
    <section className="run-tab__section" aria-label="Rozpočet">
      <h3 className="run-tab__heading">Rozpočet {data.budget && !data.budget.enrolled && <span className="run-tab__muted">· karta nemá pravidla běhů</span>}</h3>
      <div className="run-tab__meters">{meters.map(item => <div key={item.key} className="run-tab__meter" data-oh-budget={item.key} data-oh-value={item.text}>
        <span>{item.label}</span><span className="run-tab__bar"><i className={`run-tab__fill run-tab__fill--${item.tone}`}
          style={{ width: `${item.max ? Math.min(100, Math.round((item.used ?? 0) / item.max * 100)) : 0}%` }} /></span><b>{item.text}</b></div>)}</div>
    </section>
    <section className="run-tab__section" aria-label="Výsledky kroků">
      <h3 className="run-tab__heading">Výsledky kroků <code className="run-tab__muted">stepResults</code></h3>
      {results.length ? <ul className="run-tab__list">{results.map(item => <li key={item.stepId} className={`run-tab__result run-tab__result--${item.status}`}
        data-oh-step-result={item.stepId} data-oh-step-status={item.status}>
        <span aria-hidden="true">{item.status === "done" ? "✓" : item.status === "failed" ? "✕" : "↷"}</span><code>{item.stepId}</code>
        <b>{item.status === "done" ? "hotovo" : item.status === "failed" ? "selhalo" : "přeskočeno"}</b>
        <span className="run-tab__muted">{item.evidence.checks.length ? `kontroly ${item.evidence.checks.length}` : ""}{item.evidence.commits.length ? ` · ${item.evidence.commits[0].slice(0, 7)}` : ""}</span>
      </li>)}</ul> : <p className="run-tab__muted">◌ Výsledky běhu zatím nenesou výsledky kroků.</p>}
    </section>
    <section className="run-tab__section" aria-label="Samokontroly agenta">
      <h3 className="run-tab__heading">Samokontroly agenta {data.gate?.mergeReadiness.selfChecks && <span className="run-tab__muted">· {data.gate.mergeReadiness.selfChecks.status}</span>}</h3>
      {checks.length ? <div className="run-tab__chips">{checks.map(item => <span key={item.name} className={`run-tab__chip run-tab__chip--${item.state}`}
        data-oh-self-check={item.name} data-oh-value={item.state}>{CHECK_GLYPH[item.state]} {item.name}</span>)}</div>
        : <p className="run-tab__muted">◌ Samokontroly se hlásí s PR (brána review).</p>}
    </section>
    {editor && <details className="run-tab__fold" data-oh-fold="agent-workspace">
      <summary>Pracovní paměť a předávka</summary>
      <AgentWorkspace key={`${project}:${workspace}:${nodeId}`} project={project} workspace={workspace} nodeId={nodeId} readOnly={editor.readOnly} />
    </details>}
    {editor && <details className="run-tab__fold" data-oh-fold="worktrees">
      <summary>Pracovní prostory (worktree) · {assigned.length}</summary>
      {assigned.length ? assigned.map(item => <p key={item.id} className="run-tab__muted" data-oh-worktree={item.id}><b>{item.actor}</b> · <code>{item.branch}</code></p>)
        : <p className="run-tab__muted">Žádný doložený pracovní prostor karty.</p>}
      <button type="button" className="run-tab__button" disabled={editor.readOnly} onClick={onWorkspace}>Připravit oddělený worktree</button>
    </details>}
  </div>;
}
