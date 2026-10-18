import { useState } from "react";
import type { AssistantSession } from "../logic/assistant-api";
import { contextUsage, metricCost, metricNumber as n, totalTokens } from "../logic/metrics";
import "../styles/metrics.css";

/** Updates keep a fixed height; the user opens details over the conversation. */
export default function Metrics({ session }: { session?: AssistantSession }) {
  const [open, setOpen] = useState(false);
  const m = session?.metrics;
  const context = contextUsage(m);
  const models = Object.entries(m?.models ?? {});
  const facts = [
    ["Tokeny CLI relace včetně pomocných agentů", n(totalTokens(m))],
    ["Odhad ceny CLI relace", metricCost(m?.costUsd)],
    ["Aktuální kontext / kapacita", `${n(context.used)} / ${n(context.capacity)}`],
    ["Zaznamenané kompakce", n(m?.compactions)],
    ["Změřené dokončené tahy / s chybou", `${n(m?.completed)} / ${n(m?.errors)}`],
    ["Celkový čas / poslední tah", `${n(m?.durationMs == null ? null : m.durationMs / 1000)} s / ${n(m?.lastDurationMs == null ? null : m.lastDurationMs / 1000)} s`],
    ["Průchody modelem / zamítnutá oprávnění", `${n(m?.steps)} / ${n(m?.denied)}`],
    ["Splnění zadání", "Neověřeno"],
  ];
  return <div className="assistant-metrics" onKeyDown={(e) => { if (e.key === "Escape" && open) { e.stopPropagation(); setOpen(false); } }}>
    <button className="assistant-metrics__summary" type="button" onClick={() => setOpen(!open)} aria-expanded={open}>
      <span title={m?.model ?? session?.model}>Claude Code · {m?.model ?? session?.model ?? "—"}</span>
      <span>Tokeny {n(totalTokens(m))}</span>
      <span>Kontext {context.percent == null ? "—" : `${context.percent} %`}</span>
      <span>{open ? "Skrýt přehled ▴" : "Spotřeba a výkon ▾"}</span>
    </button>
    {open && <section className="assistant-metrics__detail" aria-label="Spotřeba a výkon asistenta">
      <h3>Spotřeba a výkon</h3>
      <p>Integrace: Claude Code · model {m?.model ?? `${session?.model ?? "—"} (alias)`}</p>
      <p>Pomocný směrovač: {m?.router?.provider ?? "zatím nezměřen"}{m?.router && ` · ${m.router.skipped ? "přeskočen (nedostupný nebo timeout)" : "odpověděl"} · ${n(m.router.ms)} ms`}</p>
      <p>Obnova každé 4 s; tokeny a cena po dokončení tahu. Starší neměřené tahy nejsou zahrnuté v počtu tahů a času.</p>
      <dl className="assistant-metrics__facts">{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      {context.percent != null && <progress aria-label="Zaplnění kontextu" max={100} value={Math.min(100, context.percent)} />}
      <p>Odhad USD není faktura ani čerpání předplatného. Kvóta předplatného a cena pomocného směrovače nejsou dostupné. Dokončený tah neznamená ověřené splnění zadání; přerušený tah nemusí mít závěrečnou spotřebu.</p>
      {models.length > 0 && <div className="assistant-metrics__table"><table>
        <caption>CLI relace podle modelů (kumulativně)</caption>
        <thead><tr><th>Model</th><th>Vstup</th><th>Výstup</th><th>Cache čtení</th><th>Cache zápis</th><th>Odhad USD</th></tr></thead>
        <tbody>{models.map(([model, v]) => <tr key={model}><th>{model}</th><td>{n(v.inputTokens)}</td><td>{n(v.outputTokens)}</td><td>{n(v.cacheReadInputTokens)}</td><td>{n(v.cacheCreationInputTokens)}</td><td>{metricCost(v.costUSD)}</td></tr>)}</tbody>
      </table></div>}
      <h4>Poslední tah hlavního asistenta</h4>
      <p>Vstup {n(m?.lastUsage?.input_tokens)} · výstup {n(m?.lastUsage?.output_tokens)} · cache čtení {n(m?.lastUsage?.cache_read_input_tokens)} · cache zápis {n(m?.lastUsage?.cache_creation_input_tokens)}</p>
      <p>— = údaj nebyl poskytnut. Kontext se nesčítá se spotřebou celé relace. Po vymazání kontextu CLI může začít nový součet spotřeby.</p>
      <button type="button" onClick={() => setOpen(false)}>Zavřít přehled</button>
    </section>}
  </div>;
}
