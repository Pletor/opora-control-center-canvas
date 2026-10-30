// Odznak měřáku karty ve Velínu (docs/navrhy/2026-10-30-metriky-a-spoustece.md §7, řez 4): z `gauge` agent-state
// vezme štítek složitosti (`run.label`: XS–XL nebo „?“ při chudých podkladech), % kroků, % DoD a riziko. Riziko
// `standard` se nekreslí (je to běžný stav, nic neříká). Starší server `gauge` neposílá nebo ho pošle neúplný:
// odznak pak není (null), nic se neodhaduje.

export type GaugeRisk = "elevated" | "critical";
export type GaugeBadge = {
  label: string; thin: boolean; steps: number | null; dod: number | null; risk: GaugeRisk | null;
  /** Celý popis pro titulek (štítek, kroky, DoD, riziko a důvod, model a poradce). */
  title: string;
};

const LABELS = ["XS", "S", "M", "L", "XL", "?"];
const RISK_LABEL: Record<GaugeRisk, string> = { elevated: "zvýšené riziko", critical: "kritické riziko" };
export const riskLabel = (risk: GaugeRisk) => RISK_LABEL[risk];

const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const percent = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.min(100, Math.round(value))) : null;

/** `gauge` z agent-state → model odznaku, nebo null, když štítek chybí. */
export function gaugeBadge(gauge: unknown): GaugeBadge | null {
  if (!object(gauge) || !object(gauge.run) || typeof gauge.run.label !== "string" || !LABELS.includes(gauge.run.label)) return null;
  const run = gauge.run, label = gauge.run.label;
  const thin = label === "?" || gauge.evidence === "thin";
  const steps = object(gauge.steps) ? percent(gauge.steps.percent) : null;
  const dod = object(gauge.dod) ? percent(gauge.dod.percent) : null;
  const level = object(gauge.risk) ? gauge.risk.level : null;
  const risk = level === "elevated" || level === "critical" ? level : null;
  const reasons = risk && object(gauge.risk) && Array.isArray(gauge.risk.reasons) ? gauge.risk.reasons.filter(item => typeof item === "string") : [];
  const parts = [thin ? "Složitost ? – málo podkladů, doplň kroky a soubory" : `Složitost ${label}`];
  if (steps !== null && object(gauge.steps)) parts.push(`kroky ${gauge.steps.done ?? 0}/${gauge.steps.total ?? 0} (${steps} %)`);
  if (dod !== null) parts.push(`DoD ${dod} %`);
  if (risk) parts.push(RISK_LABEL[risk] + (reasons.length ? ` (${reasons.join(", ")})` : ""));
  if (typeof run.model === "string") parts.push(`model ${run.model}` + (typeof run.advisor === "string" && run.advisor ? ` + poradce ${run.advisor}` : ""));
  return { label, thin, steps, dod, risk, title: parts.join(" · ") };
}
