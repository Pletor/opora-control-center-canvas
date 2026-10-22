import { isCount, isObject, isText } from "@/hub/oporahub-mirror/logic/hub-read";
import type { ReviewGate } from "@/hub/oporahub-review-gate/logic/review-gate";
import { reasonLabel } from "@/hub/oporahub-review-gate/logic/gate-view";

// Záložka Review & PR: nálezy review z `GET /api/oporahub/review-jobs` (vazba na PR přes repository
// + number, tedy stejné PR jako brána karty) a pravidla brány jako seznam se značkou a slovem.
export type Finding = { findingId: string; repository: string; number: number; round: number | null; severity: string; status: string;
  title: string; path: string; line: number | null; headSha: string; reviewJobId: string };

function finding(raw: unknown): Finding | null {
  if (!isObject(raw) || !isText(raw.findingId) || !isText(raw.repository) || !isCount(raw.number)) return null;
  return { findingId: raw.findingId, repository: raw.repository, number: raw.number, round: isCount(raw.round) ? raw.round : null,
    severity: isText(raw.severity) ? raw.severity : "?", status: isText(raw.status) ? raw.status : "?",
    title: isText(raw.title) ? raw.title : isText(raw.fingerprint) ? raw.fingerprint : "(bez názvu)", path: isText(raw.path) ? raw.path : "",
    line: isCount(raw.line) ? raw.line : null, headSha: isText(raw.headSha) ? raw.headSha : "", reviewJobId: isText(raw.reviewJobId) ? raw.reviewJobId : "" };
}
export function parseFindings(raw: unknown): Finding[] {
  if (!isObject(raw)) throw new Error("Review má neplatný tvar.");
  return Array.isArray(raw.findings) ? raw.findings.map(finding).filter((item): item is Finding => item !== null) : [];
}
export const reviewJobsUrl = (project: string, workspace: string) => `/api/oporahub/review-jobs?${new URLSearchParams({ project, workspace })}`;

const SEVERITY_RANK: Record<string, number> = { critical: 0, important: 1, high: 1, medium: 2, moderate: 2, minor: 3, low: 3, nit: 4, info: 5 };
export const SEVERITY_LABEL: Record<string, string> = { critical: "kritická", important: "vysoká", high: "vysoká", medium: "střední", moderate: "střední", minor: "nízká", low: "nízká", nit: "drobnost", info: "info" };
export const STATUS_LABEL: Record<string, string> = { open: "otevřený", fixed: "opraven", resolved: "vypořádán", dismissed: "zamítnut", superseded: "nahrazen" };

/** Nálezy PR karty: otevřené první, pak podle závažnosti a kola (nejnovější kolo první). */
export function cardFindings(findings: Finding[], gate: ReviewGate | null): Finding[] {
  if (!gate) return [];
  return findings.filter(item => item.repository === gate.repository && item.number === gate.number)
    .sort((a, b) => Number(b.status === "open") - Number(a.status === "open")
      || (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9) || (b.round ?? 0) - (a.round ?? 0));
}
export function severityCounts(findings: Finding[]) {
  const open = findings.filter(item => item.status === "open");
  return { open: open.length, important: open.filter(item => (SEVERITY_RANK[item.severity] ?? 9) <= 1).length, total: findings.length };
}

export type RuleRow = { code: string; label: string; state: "ok" | "pending" | "blocked" | "off"; detail: string };
const BLOCKING = new Set(["open_security_findings", "self_checks_failed", "required_checks_failed", "review_round_cap_reached",
  "open_important_findings", "changes_requested", "invalid_review_evidence"]);

/** Pravidla brány: každý důvod z API jako řádek (blokuje / čeká), plus splněná pravidla, která brána zná. */
export function gateRules(gate: ReviewGate): RuleRow[] {
  const rg = gate.reviewGate, ready = gate.mergeReadiness, reasons = new Set(rg.reasons);
  const rows: RuleRow[] = rg.reasons.map(code => ({ code, label: reasonLabel(code), state: BLOCKING.has(code) ? "blocked" : "pending", detail: "" }));
  const add = (code: string, label: string, applies: boolean, detail: string) => {
    if (applies && ![...reasons].some(reason => reason.startsWith(code))) rows.push({ code, label, state: "ok", detail });
  };
  add("template", "Šablona PR vyplněna", !!ready.template, "");
  add("required_checks", "Povinné CI kontroly zelené", !!ready.requiredChecks && Object.keys(ready.requiredChecks).length > 0, Object.keys(ready.requiredChecks ?? {}).join(", "));
  add("self_checks", "Samokontroly agenta doloženy", !!ready.selfChecks && ready.selfChecks.status === "ok", ready.selfChecks?.source ?? "");
  add("open_important", "Žádný otevřený důležitý nález", rg.openImportant === 0, "");
  add("human_approvals", `Schválení lidí ${rg.humans?.count ?? rg.humanApprovalsAtHead}/${rg.requiredHumanApprovals}`,
    (rg.humans?.count ?? rg.humanApprovalsAtHead) >= rg.requiredHumanApprovals, "");
  add("stale", `Čerstvé vůči ${ready.base?.baseRef ?? "cílové větvi"}`, !!ready.base?.fresh, "");
  if (!ready.security) rows.push({ code: "security", label: "Bezpečnostní review", state: "off", detail: "pravidlo vypnuto" });
  return rows;
}

export type Freshness = { text: string; tone: "ok" | "warn" | "gap" };
export function freshness(gate: ReviewGate): Freshness {
  const base = gate.mergeReadiness.base;
  if (!base) return { text: "čerstvost neověřena", tone: "gap" };
  return base.fresh ? { text: `aktuální vůči ${base.baseRef}`, tone: "ok" } : { text: `${base.behindBy ?? "?"} commitů za ${base.baseRef}`, tone: "warn" };
}
