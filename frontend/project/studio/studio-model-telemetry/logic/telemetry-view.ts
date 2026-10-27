// Telemetrie vybraného uzlu nebo vazby MODELu pro inspektor (prototyp `model-panels.mjs`, `modelTelemetry` a
// `node-metrics`): aktuální hodnoty jako dlaždice a krátká historie posledních ticků jako lomená čára SVG. Všechno je
// výpočet modelu (jednotky za modelovou sekundu), nikdy měření ani zápis do karet OPORY. Čistá logika bez Reactu.
import type { EdgeFlow, NodeRow } from "../../model/simulation/logic";
import { formatNumber, formatPercent, stateLabel } from "../../studio-model-run/logic/run-view";

export type Metric = { label: string; value: string; alert?: boolean };
export type Spark = { label: string; values: number[]; color: string; unit: string };

export function nodeMetrics(row: NodeRow | undefined): Metric[] {
  if (!row) return [];
  return [
    { label: "Stav", value: stateLabel(row.state), alert: row.state === "failed" },
    { label: "Dokončeno", value: `${formatNumber(row.completed || 0)}/s` },
    { label: "Přijato", value: `${formatNumber(row.offered || 0)}/s` },
    { label: "Využití", value: formatPercent(Math.min(1, row.utilization || 0)) },
    { label: "Latence", value: `${formatNumber(Math.round(row.latencyMs || 0))} ms` },
    { label: "Odmítnuto", value: `${formatNumber(row.rejected || 0)}/s`, alert: (row.rejected || 0) > 0 },
    { label: "Fronta", value: formatNumber(row.backlog || 0) },
    { label: "Úspěch závislostí", value: formatPercent(row.dependencySuccess ?? 1), alert: (row.dependencySuccess ?? 1) < .999 },
  ];
}

export function edgeMetrics(flow: EdgeFlow | undefined): Metric[] {
  if (!flow) return [];
  return [
    { label: "Nabídnuto", value: `${formatNumber(flow.offered || 0)}/s` },
    { label: "Přijato", value: `${formatNumber(flow.accepted || 0)}/s` },
    { label: "Odmítnuto", value: `${formatNumber(flow.rejected || 0)}/s`, alert: (flow.rejected || 0) > 0 },
    { label: flow.synchronous ? "Odpovědi" : "Asynchronní", value: flow.synchronous ? `${formatNumber(flow.response || 0)}/s` : "bez odpovědi" },
    { label: "Latence", value: `${formatNumber(Math.round(flow.latencyMs || 0))} ms` },
    ...(flow.slow ? [{ label: "Zpomalení", value: "konec vazby je pomalý", alert: true }] : []),
  ];
}

export const SPARK_WIDTH = 300, SPARK_HEIGHT = 56;

/** Body lomené čáry v rámečku 300 × 56 (s okrajem 4 px); měřítko od nuly do maxima řady, prázdná řada nic. */
export function sparkPoints(values: readonly number[], width = SPARK_WIDTH, height = SPARK_HEIGHT): string {
  if (!values.length) return "";
  const max = Math.max(1e-9, ...values), pad = 4, span = Math.max(1, values.length - 1);
  return values.map((value, index) => `${(pad + index / span * (width - 2 * pad)).toFixed(1)},${(height - pad - Math.max(0, value) / max * (height - 2 * pad)).toFixed(1)}`).join(" ");
}

/** Poslední hodnota a maximum řady pro popisek sparkliny. */
export const sparkRange = (values: readonly number[]) => ({ last: values.at(-1) ?? 0, max: values.length ? Math.max(...values) : 0 });
