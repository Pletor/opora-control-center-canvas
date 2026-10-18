export type ModelUsage = { inputTokens?: number; outputTokens?: number; cacheReadInputTokens?: number; cacheCreationInputTokens?: number; costUSD?: number; contextWindow?: number };
export type AssistantMetrics = {
  model?: string; completed?: number; errors?: number; durationMs?: number;
  lastDurationMs?: number | null; steps?: number; denied?: number;
  costUsd?: number | null; contextTokens?: number; compactions?: number;
  lastUsage?: Record<string, number>; models?: Record<string, ModelUsage>;
  router?: { provider?: string | null; ms?: number; skipped?: string; sources?: string[] };
};
export const metricNumber = (n: number | null | undefined) => n == null ? "—" : new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 0 }).format(n);
export const metricCost = (n: number | null | undefined) => n == null ? "nedostupný" : new Intl.NumberFormat("cs-CZ", { style: "currency", currency: "USD", maximumFractionDigits: 4 }).format(n);
export function contextUsage(m?: AssistantMetrics | null) {
  const capacity = m?.model ? m.models?.[m.model]?.contextWindow : undefined;
  const used = m?.contextTokens;
  return { capacity, used, percent: used != null && capacity && capacity > 0 ? Math.round(100 * used / capacity) : null };
}
export function totalTokens(m?: AssistantMetrics | null): number | null {
  const models = Object.values(m?.models ?? {});
  const keys = ["inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens"] as const;
  if (!models.length || models.some((v) => keys.some((k) => v[k] == null))) return null;
  return models.reduce((sum, v) => sum + keys.reduce((n, k) => n + v[k]!, 0), 0);
}
