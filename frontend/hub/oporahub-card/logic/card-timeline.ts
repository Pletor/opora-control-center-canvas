import type { AgentAction, AgentState, Health } from "@/hub/oporahub-agent-state/logic/agent-state";
import { reasonText, type Tone } from "@/hub/oporahub-agent-state/logic/loop-model";
import type { PlanChangeset } from "@/hub/plan-changes/logic/plan-changes";
import type { ExecutionSummary } from "@/hub/execution-receipts/logic/execution-receipts";

// Cesta jedné karty: základ → změny zadání → převzetí → důkazy → PR → zápis do plánu.
// Každý krok je neměnný záznam; nic se nedomýšlí (chybějící vazba = mezera, ne „v pořádku“).
export type StepKind = "baseline" | "changeset" | "claim" | "evidence" | "pr" | "writeback";
export type TimelineStep = {
  key: string; kind: StepKind; title: string; id: string; lines: string[]; tone: Tone; status: string;
  actor: "human" | "agent" | null; when: string; attrs: Record<string, string>;
};
export type CardTimeline = { steps: TimelineStep[]; forks: TimelineStep[]; latest: ExecutionSummary | null; claim: AgentAction | null };
export type CardInputs = { nodeId: string; state: AgentState | null; changesets: PlanChangeset[]; executions: ExecutionSummary[]; elapsedSeconds?: number };

const short = (value: string | null | undefined, size = 12) => value ? value.slice(0, size) : "—";
const healthTone: Record<Health, Tone> = { ok: "ok", waiting: "warn", blocking: "bad", not_connected: "gap" };

function changesetStep(item: PlanChangeset, head: string | null): TimelineStep {
  const stale = !item.accepted && item.parentRevision !== head;
  return { key: `cs:${item.id}`, kind: "changeset", title: item.accepted ? "Změna zadání" : stale ? "Zastaralý návrh" : "Návrh zadání",
    id: item.id, lines: [item.subject, `rodič ${short(item.parentRevision)}${stale ? ` ≠ hlava ${short(head)}` : ""}`, `${item.by.name} navrhl`],
    tone: item.accepted ? "ok" : stale ? "bad" : "warn", status: item.accepted ? "přijato" : stale ? "zastaralé · převést" : "čeká na přijetí",
    actor: item.by.kind === "human" ? "human" : "agent", when: item.createdAt,
    attrs: { "data-oh-changeset": item.id, "data-oh-parent": item.parentRevision, "data-oh-stale": String(stale), "data-oh-accepted": String(item.accepted) } };
}
export function executionTone(item: ExecutionSummary, elapsedSeconds = 0): { tone: Tone; status: string } {
  if (item.state === "running") return Number.isFinite(item.expiresAt) && Number.isFinite(item.serverNow) && item.expiresAt > item.serverNow + elapsedSeconds
    ? { tone: "ok", status: "běží v mezích oprávnění" } : { tone: "bad", status: "po termínu oprávnění" };
  if (item.state === "reported") return { tone: "warn", status: "nahlášeno, neověřeno" };
  return { tone: "gap", status: ({ released: "uvolněno", revoked: "oprávnění neplatí", cancelled: "zrušeno člověkem" } as Record<string, string>)[item.state] ?? item.state };
}
function claimStep(latest: ExecutionSummary | null, claim: AgentAction | null, elapsed: number): TimelineStep {
  const base = { key: "claim", kind: "claim" as const, title: "Převzetí · lease", actor: "agent" as const };
  if (latest) {
    const { tone, status } = executionTone(latest, elapsed);
    return { ...base, id: latest.executionId, tone, status, when: latest.createdAt ?? "",
      lines: [`${short(latest.executionId, 8)} · epocha ${latest.epoch}`, latest.owner ?? "vlastník nedoložen",
        latest.budget ? `pokus #${latest.budget.attempt} · oprava ${latest.budget.repairRound}` : "protokol v1 · bez rozpočtu"],
      attrs: { "data-oh-execution": latest.executionId, "data-oh-epoch": String(latest.epoch), "data-oh-execution-state": latest.state } };
  }
  if (claim) return { ...base, id: claim.id, when: "", tone: claim.status === "ready" ? "ok" : "bad",
    status: claim.status === "ready" ? "připraveno k převzetí" : `blokováno: ${claim.blockReason}`, lines: ["Zatím žádný běh."],
    attrs: { "data-oh-action-id": claim.id, "data-oh-action-status": claim.status } };
  return { ...base, id: "", when: "", tone: "gap", status: "bez běhu", lines: ["Karta nemá běh ani připravené převzetí."], attrs: {} };
}

export function cardTimeline({ nodeId, state, changesets, executions, elapsedSeconds = 0 }: CardInputs): CardTimeline {
  const head = state?.heads.acceptedHead ?? null;
  const touching = changesets.filter(item => item.changes.some(change => change.nodeId === nodeId))
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  const changes = touching.map(item => changesetStep(item, head));
  const latest = executions.filter(item => item.nodeId === nodeId)
    .sort((a, b) => (b.createdAt ?? "").localeCompare(a.createdAt ?? ""))[0] ?? null;
  const claim = state?.actions.find(item => item.verb === "claim" && item.targetId === nodeId) ?? null;
  const link = latest ? state?.actions.find(item => item.verb === "link_pull_request" && item.targetId === latest.executionId) : undefined;
  const stage = (id: string) => state?.stages.find(item => item.id === id);
  const prStage = stage("pull_request"), writeStage = stage("plan_writeback");
  // PR a zápis jsou vazby konkrétního běhu; globální zdraví etapy kartě nepřisuzujeme, chybějící vazba je mezera.
  const prTone: Tone = link?.status === "ready" ? "bad" : "gap";
  const steps: TimelineStep[] = [
    { key: "baseline", kind: "baseline", title: "Přijatý základ", id: head ?? "", lines: [short(head)], tone: head ? "ok" : "gap",
      status: head ? "přijatá hlava" : "základ chybí", actor: "human", when: "", attrs: { "data-oh-revision": head ?? "" } },
    ...changes.filter(item => item.tone !== "bad").slice(-3),
    claimStep(latest, claim, elapsedSeconds),
    { key: "evidence", kind: "evidence", title: "Důkazy", id: latest?.executionId ?? "", actor: "agent", when: "",
      lines: latest ? [`výsledek pro revizi ${short(latest.acceptedRevision)}`] : ["Žádný nahlášený výsledek."],
      tone: latest?.state === "reported" ? "warn" : "gap", status: latest?.state === "reported" ? "nahlášeno, ne ověřeno" : "bez výsledku",
      attrs: latest ? { "data-oh-evidence-for": latest.executionId } : {} },
    { key: "pr", kind: "pr", title: "PR / GitHub", id: link?.id ?? "", actor: "agent", when: "", tone: prTone,
      status: link ? link.status === "ready" ? "PR nenavázáno" : "vazba PR nenapojena" : prStage?.health === "not_connected" ? "nenapojeno" : "bez PR",
      lines: [link ? `${link.method} …/pull-request` : "Vazba běh → PR se zobrazí po napojení."],
      attrs: { "data-oh-pr-link": link ? `${link.status}${link.blockReason ? `:${link.blockReason}` : ""}` : prStage?.health ?? "" } },
    { key: "writeback", kind: "writeback", title: "Merge → plán", id: "", actor: null, when: "",
      tone: writeStage && writeStage.health !== "ok" ? healthTone[writeStage.health] : "gap",
      status: writeStage?.health === "not_connected" ? "nenapojeno" : writeStage ? reasonText[writeStage.reason] ?? writeStage.reason : "neznámé",
      lines: ["Po merge se nová revize plánu nevytváří automaticky; kartu uzavírá člověk."], attrs: { "data-oh-writeback": writeStage?.health ?? "not_connected" } },
  ];
  return { steps, forks: changes.filter(item => item.tone === "bad"), latest, claim };
}
