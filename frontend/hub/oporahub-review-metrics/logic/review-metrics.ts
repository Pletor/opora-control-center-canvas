import { isCount, isObject } from "@/hub/oporahub-mirror/logic/hub-read";

// Metriky review (docs/oporahub-review-identity.md, „Metriky“): přísný parser a čistý view-model infografiky.
export type Rate = number | null;
export type ReviewMetricsDoc = {
  window: string; prsReviewed: number;
  findingsBySeverity: { important: number; nit: number; pre_existing: number };
  findingOutcomes: { fixed: number; resolvedWithoutFix: number; rejectedByVoters: number; open: number };
  findingAcceptanceRate: Rate; voterRejectionRate: Rate;
  roundsPerPr: { mean: Rate; max: number }; securityRounds: { mean: Rate; max: number };
  humanApprovalsPerPr: Rate;
  timeToHumanDecisionSeconds: { samples: number; median: Rate; mean: Rate };
  guardrails: { revertRate: Rate; incidentRate: Rate }; truncated: boolean;
};
export const WINDOWS = ["7d", "30d", "90d", "all"] as const;
export type MetricsWindow = typeof WINDOWS[number];

const rate = (value: unknown): value is Rate => value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0);
const counts = (value: unknown, keys: string[]) => isObject(value) && keys.every(key => isCount(value[key]));

export function parseReviewMetrics(raw: unknown): ReviewMetricsDoc {
  const fail = () => { throw new Error("Metriky review mají neplatný tvar."); };
  if (!isObject(raw) || typeof raw.window !== "string" || !isCount(raw.prsReviewed)) return fail();
  if (!counts(raw.findingsBySeverity, ["important", "nit", "pre_existing"])) return fail();
  if (!counts(raw.findingOutcomes, ["fixed", "resolvedWithoutFix", "rejectedByVoters", "open"])) return fail();
  if (![raw.findingAcceptanceRate, raw.voterRejectionRate, raw.humanApprovalsPerPr].every(rate)) return fail();
  for (const key of ["roundsPerPr", "securityRounds"] as const) {
    const value = raw[key];
    if (!isObject(value) || !rate(value.mean) || !isCount(value.max)) return fail();
  }
  const time = raw.timeToHumanDecisionSeconds, guard = raw.guardrails;
  if (!isObject(time) || !isCount(time.samples) || !rate(time.median) || !rate(time.mean)) return fail();
  if (!isObject(guard) || !rate(guard.revertRate) || !rate(guard.incidentRate)) return fail();
  const doc = raw as unknown as ReviewMetricsDoc;
  return { window: doc.window, prsReviewed: doc.prsReviewed, findingsBySeverity: doc.findingsBySeverity, findingOutcomes: doc.findingOutcomes,
    findingAcceptanceRate: doc.findingAcceptanceRate, voterRejectionRate: doc.voterRejectionRate, roundsPerPr: doc.roundsPerPr,
    securityRounds: doc.securityRounds, humanApprovalsPerPr: doc.humanApprovalsPerPr, timeToHumanDecisionSeconds: doc.timeToHumanDecisionSeconds,
    guardrails: doc.guardrails, truncated: raw.truncated === true };
}
export function parseEvalCount(raw: unknown): number {
  if (!isObject(raw) || !Array.isArray(raw.items)) throw new Error("Eval sada má neplatný tvar.");
  return raw.items.length;
}

const scope = (project: string, workspace: string) => new URLSearchParams({ project, workspace });
export const metricsUrl = (project: string, workspace: string, window: MetricsWindow) =>
  `/api/oporahub/review-metrics?${new URLSearchParams({ project, workspace, window })}`;
export const evalsUrl = (project: string, workspace: string) => `/api/oporahub/review-evals?${scope(project, workspace)}`;
export const evalExportUrl = (project: string, workspace: string) => `/api/oporahub/review-evals/export.jsonl?${scope(project, workspace)}`;

export function percent(value: Rate) { return value === null ? "bez dat" : `${Math.round(value * 1000) / 10} %`; }
/** Lidský čas: sekundy, minuty, hodiny nebo dny podle velikosti. */
export function duration(seconds: Rate) {
  if (seconds === null) return "bez dat";
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 86400) return `${Math.round(seconds / 360) / 10} h`;
  return `${Math.round(seconds / 8640) / 10} d`;
}

export type Tone = "ok" | "warn" | "bad" | "gap" | "acc";
export type Bar = { metric: string; label: string; value: number; pct: number; tone: Tone };
export type Tile = { metric: string; label: string; value: string; raw: number | null; tone: Tone; hint: string };
export type MetricsView = { severity: Bar[]; outcomes: Bar[]; tiles: Tile[]; guardrails: Tile[]; prsReviewed: number; truncated: boolean };

function bars(group: string, entries: [string, string, number, Tone][]): Bar[] {
  const max = Math.max(1, ...entries.map(entry => entry[2]));
  return entries.map(([key, label, value, tone]) => ({ metric: `${group}.${key}`, label, value, pct: Math.round(value / max * 100), tone }));
}
const fixed = (value: Rate) => value === null ? null : Math.round(value * 10000) / 10000;

export function metricsView(doc: ReviewMetricsDoc): MetricsView {
  const s = doc.findingsBySeverity, o = doc.findingOutcomes, accept = doc.findingAcceptanceRate;
  const noise = accept === null ? null : fixed(1 - accept);
  const time = doc.timeToHumanDecisionSeconds;
  const guard = (metric: string, label: string, value: Rate, hint: string): Tile => ({ metric, label, value: percent(value), raw: value,
    tone: value === null ? "gap" : value > 0 ? "warn" : "ok", hint });
  return {
    prsReviewed: doc.prsReviewed, truncated: doc.truncated,
    severity: bars("findingsBySeverity", [["important", "důležité", s.important, "bad"], ["nit", "drobnosti", s.nit, "warn"], ["pre_existing", "už existující", s.pre_existing, "gap"]]),
    outcomes: bars("findingOutcomes", [["fixed", "opraveno", o.fixed, "ok"], ["resolvedWithoutFix", "vypořádáno bez opravy", o.resolvedWithoutFix, "warn"],
      ["rejectedByVoters", "zamítli ověřovatelé", o.rejectedByVoters, "gap"], ["open", "otevřené", o.open, "acc"]]),
    tiles: [
      { metric: "findingAcceptanceRate", label: "Přijetí nálezů", value: percent(accept), raw: accept, tone: accept === null ? "gap" : "ok", hint: "opraveno / (opraveno + bez opravy)" },
      { metric: "noiseRate", label: "Šum", value: percent(noise), raw: noise, tone: noise === null ? "gap" : noise > 0.5 ? "warn" : "ok", hint: "1 − přijetí (reakce autora)" },
      { metric: "voterRejectionRate", label: "Odfiltrováno hlasováním", value: percent(doc.voterRejectionRate), raw: doc.voterRejectionRate, tone: "acc", hint: "kandidáti bez potřebných hlasů" },
      { metric: "roundsPerPr.mean", label: "Kola na PR", value: doc.roundsPerPr.mean === null ? "bez dat" : `${doc.roundsPerPr.mean.toFixed(1)} (max ${doc.roundsPerPr.max})`,
        raw: doc.roundsPerPr.mean, tone: "acc", hint: `bezpečnostní: ${doc.securityRounds.mean?.toFixed(1) ?? "—"} · max ${doc.securityRounds.max}` },
      { metric: "timeToHumanDecisionSeconds.median", label: "Čas do rozhodnutí člověka", value: duration(time.median), raw: time.median, tone: time.median === null ? "gap" : "acc",
        hint: `průměr ${duration(time.mean)} · ${time.samples} vzorků` },
    ],
    guardrails: [guard("guardrails.revertRate", "Reverty", doc.guardrails.revertRate, "podíl PR s revertem"),
      guard("guardrails.incidentRate", "Incidenty", doc.guardrails.incidentRate, "podíl PR s incidentem")],
  };
}
