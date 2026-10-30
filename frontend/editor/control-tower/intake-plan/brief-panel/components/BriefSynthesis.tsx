// Co srdce z požadavku pochopilo: cíl a pro koho, úplný seznam částí s původem (od vás, z rešerše, odvozeno),
// kritéria přijetí s tím, čím se ověří, a hranice „co ne“. Jen zobrazuje hotový model, nic neposílá.
import type { BriefSynthesis as Synthesis } from "../logic/brief-model";

export default function BriefSynthesis({ synthesis, open }: { synthesis: Synthesis; open: boolean }) {
  return (
    <details className="brief-panel__synthesis" open={open}>
      <summary className="brief-panel__summary">Co srdce pochopilo</summary>
      {synthesis.goal && <p className="brief-panel__goal">{synthesis.goal}</p>}
      {synthesis.users && <p className="brief-panel__users">Pro koho: {synthesis.users}</p>}
      {synthesis.parts.length > 0 && <section className="brief-panel__section" aria-label="Části">
        <span className="brief-panel__label">Z čeho se to skládá</span>
        <ul className="brief-panel__list">
          {synthesis.parts.map((part, index) => (
            <li key={index} className="brief-panel__part">
              <span>{part.text}</span>
              <small className={`brief-panel__origin brief-panel__origin--${part.origin}`} title={part.source ?? undefined}>
                {part.originText}{part.source ? `: ${part.source}` : ""}
              </small>
            </li>
          ))}
        </ul>
      </section>}
      {synthesis.acceptance.length > 0 && <section className="brief-panel__section" aria-label="Kritéria přijetí">
        <span className="brief-panel__label">Hotovo je, když</span>
        <ul className="brief-panel__list">
          {synthesis.acceptance.map((item, index) => (
            <li key={index} className="brief-panel__criterion">
              <span>{item.text}</span>
              {item.checkText && <small className="brief-panel__check">{item.checkText}</small>}
            </li>
          ))}
        </ul>
      </section>}
      {synthesis.outOfScope.length > 0 && <section className="brief-panel__section" aria-label="Co ne">
        <span className="brief-panel__label">Co se dělat nebude</span>
        <ul className="brief-panel__list">
          {synthesis.outOfScope.map((item, index) => <li key={index} className="brief-panel__boundary">{item}</li>)}
        </ul>
      </section>}
    </details>
  );
}
