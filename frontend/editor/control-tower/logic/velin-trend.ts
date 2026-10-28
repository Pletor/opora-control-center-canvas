// Trend ve Velínu (docs/strazci.md §5): malé křivky souhrnných čísel z `GET /api/strazci/trend?project=`, které strážce
// `trend` vzorkuje každých 15 min. Čisté funkce: ověření odpovědi (neplatná = null, nic se nekreslí) a body křivky.
export type TrendPoint = { at: string; value: number };
export type TrendSeries = Record<string, TrendPoint[]>;
export type TrendDirection = "up" | "down";
export type TrendLine = {
  id: string; label: string; good: TrendDirection; points: TrendPoint[]; last: number | null; delta: number | null;
  tone: "better" | "worse" | "same"; path: string;
};

/** Pořadí a jména čísel ve Velínu; `good` říká, kterým směrem je změna k lepšímu (barva rozdílu). */
export const TREND_METRICS: { id: string; label: string; good: TrendDirection }[] = [
  { id: "holes", label: "Díry mapy", good: "down" },
  { id: "holes.agent", label: "Díry pro agenty", good: "down" },
  { id: "journeys.verified", label: "Ověřené cesty", good: "up" },
  { id: "journeys.total", label: "Cesty celkem", good: "up" },
  { id: "cards.done", label: "Hotové karty", good: "up" },
  { id: "cards.building", label: "Staví se", good: "up" },
  { id: "work.stalled", label: "Zaseknutá práce", good: "down" },
  { id: "proposals.waiting", label: "Návrhy čekají", good: "down" },
];

const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const point = (value: unknown): value is TrendPoint => object(value) && typeof value.at === "string" && Number.isFinite(value.value);

/** Ověří odpověď `GET /api/strazci/trend`; vrací řady podle čísla, neplatná odpověď = null. */
export function parseTrend(raw: unknown): TrendSeries | null {
  if (!object(raw) || !object(raw.series)) return null;
  const series = raw.series;
  const valid = Object.values(series).every(items => Array.isArray(items) && items.every(point));
  return valid ? series as TrendSeries : null;
}

/** SVG cesta křivky v rámu `width × height`; x podle času vzorku, y od minima k maximu řady (rovná řada = čára uprostřed). */
export function sparkPath(points: TrendPoint[], width: number, height: number): string {
  if (!points.length) return "";
  const times = points.map(item => Date.parse(item.at));
  const first = Math.min(...times), span = Math.max(...times) - first;
  const values = points.map(item => item.value);
  const low = Math.min(...values), range = Math.max(...values) - low;
  const x = (time: number) => span ? ((time - first) / span) * width : width;
  const y = (value: number) => range ? height - ((value - low) / range) * height : height / 2;
  const coords = points.map((item, index) => `${x(times[index]).toFixed(1)},${y(item.value).toFixed(1)}`);
  const pairs = points.length === 1 ? [`0.0,${y(values[0]).toFixed(1)}`, ...coords] : coords;
  return pairs.map((pair, index) => (index ? "L" : "M") + pair).join(" ");
}

/** Řádky panelu Trend v pevném pořadí; číslo bez vzorku má prázdnou křivku a `last` null. */
export function trendLines(series: TrendSeries, width: number, height: number): TrendLine[] {
  return TREND_METRICS.map(metric => {
    const points = series[metric.id] ?? [];
    const last = points.length ? points[points.length - 1].value : null;
    const delta = last !== null && points.length > 1 ? last - points[0].value : null;
    const tone = !delta ? "same" : (delta > 0) === (metric.good === "up") ? "better" : "worse";
    return { ...metric, points, last, delta, tone, path: sparkPath(points, width, height) };
  });
}
