import type { PletorAction } from "../logic/linie-summary";

type Props = {
  lines: string[]; next: string; builtAt: string;
  ages: { name: string; text: string; stale: boolean }[];
  actions: PletorAction[]; flash: string; onAct: (id: string) => void;
};

/**
 * Panel Pletora vpravo nahoře: výrok z jednoho vyhodnocení (jen osy a souhrn), další krok týmž textem jako v detailu,
 * čas sestavení snímku a stáří každého zdroje zvlášť, pak akce – povolené jako tlačítka, zakázané šedé s důvodem.
 * Pole „Zadat srdci“ je zatím zavřené: tok žádostí přijde s /api/pletor/requests, falešný tok tu není.
 */
export default function LiniePletor({ lines, next, builtAt, ages, actions, flash, onAct }: Props) {
  return (
    <section className="pletor-dashboard__linie-pletor" aria-label="Pletor – ověřený stav">
      <h2 className="pletor-dashboard__linie-pletor-h">Pletor · ověřený stav</h2>
      <p className="pletor-dashboard__linie-pletor-say">{lines.join(" ")}</p>
      {next && <p className="pletor-dashboard__linie-pletor-next"><strong>Další krok:</strong> {next}</p>}
      <p className="pletor-dashboard__linie-pletor-meta">
        {builtAt ? `snímek sestaven ${builtAt}` : "snímek bez stáří zdrojů"} · chybějící data = „nevím“, ne „není“
      </p>
      {ages.length > 0 && (
        <p className="pletor-dashboard__linie-pletor-meta">
          {ages.map((age) => (
            <span key={age.name} className={`pletor-dashboard__linie-pletor-age${age.stale ? " pletor-dashboard__linie-pletor-age--stale" : ""}`}>{age.text}</span>
          ))}
        </p>
      )}
      {actions.length > 0 && (
        <span className="pletor-dashboard__tools pletor-dashboard__linie-acts">
          {actions.map((action) => (
            <button key={action.id} type="button" className="pletor-dashboard__button" disabled={!action.enabled} title={action.why || undefined}
              onClick={() => onAct(action.id)}>{action.label}</button>
          ))}
        </span>
      )}
      {flash && <p className="pletor-dashboard__linie-flash" role="status">{flash}</p>}
      <textarea className="pletor-dashboard__input pletor-dashboard__linie-pletor-ask" disabled aria-label="Zadat srdci"
        placeholder="Změna plánu nebo zadání… Pletor zapíše „žádost přijata“; plán, ticket, relace a commit se objeví až po potvrzení." />
      <p className="pletor-dashboard__note">Zadat srdci: čeká na /api/pletor/requests (L7 PR 5).</p>
    </section>
  );
}
