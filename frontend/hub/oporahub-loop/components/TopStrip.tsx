import type { StripView } from "@/hub/oporahub-agent-state/logic/strip-model";
import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import { ToneChip } from "@/hub/oporahub-health/components/HealthMark";

/** Horní pás: přijatá hlava, drift, mix rizika a nejvýše tři rozhodnutí, která patří člověku. */
export default function TopStrip({ strip, open }: { strip: StripView; open: (target: DetailTarget) => void }) {
  const { risk } = strip;
  return <div className="oporahub-loop__strip">
    <section className="oporahub-loop__tile" data-oh-field="acceptedHead" data-oh-value={strip.head ?? ""}>
      <span className="oporahub-loop__label">Přijatá hlava</span>
      <code className={strip.head ? "oporahub-loop__hash" : "oporahub-loop__hash oporahub-loop__hash--none"}>{strip.headShort}</code>
      <button type="button" className="oporahub-loop__link-button" onClick={() => open({ kind: "graph", title: "Kontrola přijatého plánu" })}>Otevřít plán</button>
    </section>
    <section className="oporahub-loop__tile" data-oh-field="drift" data-oh-value={String(strip.workingDiffers)}>
      <span className="oporahub-loop__label">Drift pracovní verze</span>
      <span className="oporahub-loop__row">{strip.workingDiffers ? <ToneChip tone="warn">◷ liší se od přijaté</ToneChip> : <ToneChip tone="ok">✓ odpovídá přijaté</ToneChip>}</span>
      <span className="oporahub-loop__sub" data-oh-field="staleProposals" data-oh-value={strip.staleCount}>{strip.staleCount} návrhů na starém základu</span>
    </section>
    <section className="oporahub-loop__tile" data-oh-field="riskMix" data-oh-value={`${risk.low}/${risk.elevated}/${risk.critical}`}>
      <span className="oporahub-loop__label">Riziko čekajících · {risk.total}</span>
      <span className="oporahub-loop__risk" role="img" aria-label={`${risk.low} nízké, ${risk.elevated} zvýšené, ${risk.critical} kritické`}>
        <i className="oporahub-loop__risk-part oporahub-loop__risk-part--low" style={{ width: `${risk.pct.low}%` }} />
        <i className="oporahub-loop__risk-part oporahub-loop__risk-part--elevated" style={{ width: `${risk.pct.elevated}%` }} />
        <i className="oporahub-loop__risk-part oporahub-loop__risk-part--critical" style={{ width: `${risk.pct.critical}%` }} />
      </span>
      <span className="oporahub-loop__row oporahub-loop__sub">
        <span data-oh-risk="low">● <b>{risk.low}</b> nízké</span><span data-oh-risk="elevated">▲ <b>{risk.elevated}</b> zvýšené</span><span data-oh-risk="critical">■ <b>{risk.critical}</b> kritické</span>
      </span>
    </section>
    <section className="oporahub-loop__tile oporahub-loop__tile--decisions" data-oh-field="decisions" data-oh-value={strip.decisions.length}>
      <span className="oporahub-loop__row oporahub-loop__row--between">
        <span className="oporahub-loop__label oporahub-loop__label--human">Potřebuje vaše rozhodnutí · {strip.decisions.length}</span>
        <button type="button" className="oporahub-loop__link-button" onClick={() => open({ kind: "history", title: "Historie a všechny návrhy" })}>všechny návrhy</button>
      </span>
      {strip.decisions.map(item => <div className="oporahub-loop__decision" key={item.id} data-oh-decision={item.id} data-oh-action-id={item.actionId}>
        <ToneChip tone={item.tone}>{item.kindLabel}</ToneChip><b className="oporahub-loop__decision-title">{item.title}</b>
        <button type="button" className="oporahub-loop__button" onClick={() => open(item.target)}>{item.button}</button>
      </div>)}
      {!strip.decisions.length && <span className="oporahub-loop__sub">Nic nečeká na vaše rozhodnutí.</span>}
    </section>
  </div>;
}
