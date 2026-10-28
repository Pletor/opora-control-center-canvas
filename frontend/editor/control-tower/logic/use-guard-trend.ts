// Trend strážců pro panel Velínu: `GET /api/strazci/trend?project=&days=14` sdíleným pollerem jednou za 5 min (strážce
// `trend` vzorkuje každých 15 min). Chyba čtení nechá poslední známé řady; neplatná odpověď = null.
import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { parseTrend, type TrendSeries } from "./velin-trend";

const POLL_MS = 5 * 60_000;
const DAYS = 14;

export function useGuardTrend(project: string): TrendSeries | null {
  const [trend, setTrend] = useState<{ project: string; value: TrendSeries | null } | null>(null);
  usePolling(async () => {
    try {
      const raw = await api<unknown>(`/api/strazci/trend?project=${encodeURIComponent(project)}&days=${DAYS}`);
      setTrend({ project, value: parseTrend(raw) });
    } catch { /* poslední známé řady zůstávají */ }
  }, { intervalMs: POLL_MS, refreshKeys: [project] });
  return trend?.project === project ? trend.value : null;
}
