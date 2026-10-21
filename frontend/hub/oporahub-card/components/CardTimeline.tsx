import type { CSSProperties } from "react";
import type { TimelineStep } from "../logic/card-timeline";
import { ToneChip } from "@/hub/oporahub-health/components/HealthMark";

const when = (value: string) => {
  const time = Date.parse(value);
  return Number.isFinite(time) ? new Date(time).toLocaleString("cs-CZ", { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";
};
const glyph = { ok: "✓", warn: "◷", bad: "✕", gap: "◌" } as const;

function Step({ step, onOpen }: { step: TimelineStep; onOpen?: () => void }) {
  return <article className={`oporahub-card__step oporahub-card__step--${step.tone}`} {...step.attrs} data-oh-step={step.kind}>
    <h3 className="oporahub-card__step-title">{step.title}
      {step.actor && <span className={`oporahub-card__avatar oporahub-card__avatar--${step.actor}`} aria-label={step.actor === "human" ? "člověk" : "agent"}>{step.actor === "human" ? "Č" : "A"}</span>}</h3>
    {step.id && <code className="oporahub-card__id" title={step.id}>{step.id.slice(0, 16)}</code>}
    {step.lines.map(line => <span key={line} className="oporahub-card__line">{line}</span>)}
    <ToneChip tone={step.tone}>{glyph[step.tone]} {step.status}</ToneChip>
    {onOpen && <button type="button" className="oporahub-card__ghost" onClick={onOpen}>{step.tone === "bad" ? "Převést (rebase)" : "Otevřít"}</button>}
  </article>;
}

/** Vodorovná cesta karty: piny na ose, čas pod nimi a krok pod časem; zastaralé návrhy visí nad osou. */
export default function CardTimeline({ steps, forks, onOpen }: { steps: TimelineStep[]; forks: TimelineStep[]; onOpen: (step: TimelineStep) => void }) {
  const columns = { "--oh-steps": steps.length } as CSSProperties;
  return <section className="oporahub-card__panel" aria-label="Cesta karty">
    <header className="oporahub-card__panel-head"><h2 className="oporahub-card__title">Cesta karty</h2>
      <span className="oporahub-card__note">každý krok je neměnný záznam · vazby jsou na revizi a běh</span></header>
    {forks.length > 0 && <div className="oporahub-card__forks">
      <span className="oporahub-card__lane">Větev: zastaralé návrhy na jiném základu</span>
      {forks.map(step => <Step key={step.key} step={step} onOpen={() => onOpen(step)} />)}
    </div>}
    <ol className="oporahub-card__track" style={columns}>
      {steps.map(step => <li key={step.key} className="oporahub-card__stop">
        <span className={`oporahub-card__pin oporahub-card__pin--${step.tone}`} aria-hidden="true" />
        <span className="oporahub-card__when">{step.when ? when(step.when) : "—"}</span>
        <Step step={step} onOpen={step.kind === "changeset" || step.kind === "claim" ? () => onOpen(step) : undefined} />
      </li>)}
    </ol>
  </section>;
}
