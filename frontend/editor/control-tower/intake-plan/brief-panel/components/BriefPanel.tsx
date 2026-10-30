// Panel výslechu u požadavku (docs/navrhy/2026-10-30-vyslech-srdce.md §7, řez 3). Se spisem: stav, otevřené
// otázky s doporučením, co srdce pochopilo a co ještě chybí, nakonec vaše dřívější odpovědi. Bez spisu jen tlačítko
// „Vyslechni mě k tomu“. Rodič skládá dílky a hlásí odpovědi a spuštění přes `actions` nahoru do `IntakePlan`.
import { briefKey, type BriefActions, type BriefView } from "../logic/brief-model";
import BriefQuestion from "./BriefQuestion";
import BriefSynthesis from "./BriefSynthesis";
import "../styles/brief-panel.css";

type Props = { requirement: string; brief: BriefView | null; actions: BriefActions };

export default function BriefPanel({ requirement, brief, actions }: Props) {
  if (!brief) {
    const key = briefKey(requirement);
    return (
      <div className="brief-panel brief-panel--empty">
        <button type="button" className="brief-panel__button" disabled={actions.busy !== null}
          onClick={() => actions.onStart(requirement)} data-oh-action="brief-start">Vyslechni mě k tomu</button>
        {actions.busy === key && <small className="brief-panel__muted">Budím srdce…</small>}
        {actions.errors[key] && <p className="brief-panel__error" role="alert">{actions.errors[key]}</p>}
      </div>
    );
  }
  return (
    <section className={`brief-panel brief-panel--${brief.tone}`} aria-label="Výslech srdce" data-oh-brief={brief.status}>
      <p className="brief-panel__status">{brief.statusText}</p>
      {brief.open.length > 0 && <ol className="brief-panel__questions" aria-label="Otázky srdce">
        {brief.open.map(question => {
          const key = briefKey(requirement, question.id);
          return <BriefQuestion key={question.id} question={question} busy={actions.busy === key} error={actions.errors[key] ?? null}
            onAnswer={answer => actions.onAnswer(requirement, question.id, answer)} />;
        })}
      </ol>}
      {brief.synthesis && <BriefSynthesis synthesis={brief.synthesis} open={brief.open.length === 0} />}
      {!brief.synthesis && <p className="brief-panel__muted">Pochopení zatím není sepsané.</p>}
      {brief.missing.length > 0 && <section className="brief-panel__section" aria-label="Co ještě chybí">
        <span className="brief-panel__label">Do jasna ještě chybí</span>
        <ul className="brief-panel__list">
          {brief.missing.map(item => <li key={item} className="brief-panel__missing">{item}</li>)}
        </ul>
      </section>}
      {brief.answered.length > 0 && <details className="brief-panel__answered">
        <summary className="brief-panel__summary">Vaše odpovědi · {brief.answered.length}</summary>
        <ul className="brief-panel__list">
          {brief.answered.map(item => (
            <li key={item.id} className="brief-panel__reply">
              <span>{item.text}</span>
              <small className="brief-panel__muted">{item.accepted ? "potvrzeno doporučení: " : "odpověděli jste: "}{item.answer}</small>
            </li>
          ))}
        </ul>
      </details>}
    </section>
  );
}
