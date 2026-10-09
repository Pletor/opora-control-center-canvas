import type { Usage } from "../logic/use-usage";

export default function CardUsage({ usage, sector }: { usage?: Usage; sector: boolean }) {
  const number = (value: number | null | undefined) => value == null ? "nedostupné" : value.toLocaleString("cs-CZ");
  return <div className="node-card__usage" title="Údaje hlášené agentem; částky v penězích se neodhadují.">
    <small>{sector ? "Součet sektoru · " : ""}Tokeny: {number(usage?.tokens)} · Čas: {usage?.durationMs == null ? "nedostupné" : `${number(usage.durationMs / 1000)} s`} · Pokusy: {number(usage?.attempts)}</small>
  </div>;
}
