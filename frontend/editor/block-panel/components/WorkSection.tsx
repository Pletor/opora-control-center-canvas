// „Práce na kartě“: čip stavu a jedna věta (etapa · krok X z Y, zaseklý krok, na co karta čeká), segmenty kroků,
// kroky ✓/…/✗ s kontrolou nebo commitem, kdo kartu drží a kolik zbývá (nebo kdy ji uvolnil), další krok, PR
// s počtem commitů a co chybí k hotovu. Řádka „teď: …“ jen když kartu někdo právě drží.
import PrBadge from "@/shared/pr-badge/components/PrBadge";
import { useNow } from "@/editor/canvas/card-face/logic/use-now";
import type { WorkView } from "../logic/panel-work";
import { remaining } from "../logic/panel-work";
import { clock, whoName } from "../logic/trail-timeline";
import SourceMark from "./SourceMark";

function Holder({ holder }: { holder: NonNullable<WorkView["holder"]> }) {
  const now = useNow(30_000, !!holder.until);
  const who = whoName(holder.name);
  const left = remaining(holder.until, now);
  return <>
    <span className={"block-panel__who block-panel__who--" + who.kind}><i aria-hidden="true">{who.kind === "heart" ? "✦" : who.kind === "human" ? "H" : "A"}</i>{who.name}</span>
    {holder.until && <span className="block-panel__muted" data-oh-lease-expires={holder.until}>do {clock(holder.until)}{left && " · " + left}</span>}
  </>;
}

export default function WorkSection({ work, live }: { work: WorkView; live: { text: string; at: string } | null }) {
  return (
    <section className="block-panel__sec" aria-label="Práce na kartě">
      <h3 className="block-panel__h">Práce na kartě<span className="block-panel__h-meta">⚙ ze stopy</span></h3>
      <div className="block-panel__status">
        <span className={"block-panel__chip block-panel__chip--" + work.chip.tone}>{[work.chip.glyph, work.chip.word].filter(Boolean).join(" ")}</span>
        <span>{work.line}</span>
      </div>
      {work.steps.length > 0 && <div className="block-panel__segs" aria-hidden="true">
        {work.steps.map((step) => <b key={step.id} className={"block-panel__seg block-panel__seg--" + step.tone} />)}
      </div>}
      {live && <div className="block-panel__live"><span className="block-panel__live-dot" aria-hidden="true" />teď: {live.text}<span className="block-panel__muted"> · {clock(live.at)}</span></div>}
      {work.steps.length > 0 ? <ul className="block-panel__steps">
        {work.steps.map((step) => <li key={step.id} className={"block-panel__step block-panel__step--" + step.tone} data-oh-step={step.id}>
          <span className="block-panel__step-mark" aria-hidden="true">{step.glyph}</span>
          <span className="block-panel__step-id">{step.id}</span>
          <span className="block-panel__step-title">{step.title}</span>
          <span className="block-panel__step-note">{step.note}</span>
        </li>)}
      </ul> : <p className="block-panel__empty">Karta zatím nemá kroky plánu. Naplánuje je srdce.</p>}
      {work.untouched && <p className="block-panel__empty">Na kartě zatím nikdo nepracoval. Až ji dělník převezme branou, objeví se tu kdo, do kdy a co udělal.</p>}
      <dl className="block-panel__kv">
        <dt>Drží</dt><dd>{work.holder ? <Holder holder={work.holder} />
          : <span className="block-panel__muted">nikdo{work.released && ` · uvolněno ${clock(work.released)}`}</span>}</dd><SourceMark source="det" />
        {work.next && <><dt>Další krok</dt><dd>{work.next}</dd><SourceMark source="det" /></>}
        {work.pr && <><dt>PR</dt><dd><PrBadge badge={work.pr} />{work.commits && <span className="block-panel__muted">{work.commits}</span>}</dd><SourceMark source="det" /></>}
        {work.missing.length > 0 && <><dt>Chybí k hotovu</dt><dd className="block-panel__missing">
          {work.missing.map((item) => <span key={item} className="block-panel__chip block-panel__chip--gap">{item}</span>)}
        </dd><SourceMark source="det" /></>}
      </dl>
    </section>
  );
}
