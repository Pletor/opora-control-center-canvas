import type { PletorAction } from "../logic/linie-actions";
import type { HeartRequest } from "../logic/linie-requests";
import LinieActions from "./LinieActions";
import LinieRequests from "./LinieRequests";

type Props = {
  lines: string[]; next: string; builtAt: string;
  /** Výpadek čtení boardu („poslední úspěšné čtení před N min · nyní nedostupné“), jinak prázdné. */
  feed: string;
  ages: { name: string; text: string; stale: boolean }[];
  actions: PletorAction[]; note: string; onNote: (note: string) => void; flash: string; onAct: (id: string) => void;
  requests: HeartRequest[] | null; onAsk: (text: string) => Promise<string>;
};

/**
 * Panel Pletora vpravo nahoře: výrok z jednoho vyhodnocení (jen osy a souhrn), další krok týmž textem jako v detailu,
 * čas sestavení snímku a stáří každého zdroje zvlášť, pak akce – povolené jako tlačítka, zakázané šedé s důvodem –
 * a pole „Zadat srdci“ s řetězci žádostí.
 */
export default function LiniePletor({ lines, next, builtAt, feed, ages, actions, note, onNote, flash, onAct, requests, onAsk }: Props) {
  return (
    <section className="pletor-dashboard__linie-pletor" aria-label="Pletor – ověřený stav">
      <h2 className="pletor-dashboard__linie-pletor-h">Pletor · ověřený stav</h2>
      <p className="pletor-dashboard__linie-pletor-say">{lines.join(" ")}</p>
      {next && <p className="pletor-dashboard__linie-pletor-next"><strong>Další krok:</strong> {next}</p>}
      <p className="pletor-dashboard__linie-pletor-meta">
        {builtAt ? `snímek sestaven ${builtAt}` : "snímek bez stáří zdrojů"} · chybějící data = „nevím“, ne „není“
      </p>
      {feed && <p className="pletor-dashboard__linie-pletor-meta"><span className="pletor-dashboard__linie-pletor-age--stale">{feed}</span></p>}
      {ages.length > 0 && (
        <p className="pletor-dashboard__linie-pletor-meta">
          {ages.map((age) => (
            <span key={age.name} className={`pletor-dashboard__linie-pletor-age${age.stale ? " pletor-dashboard__linie-pletor-age--stale" : ""}`}>{age.text}</span>
          ))}
        </p>
      )}
      <LinieActions actions={actions} note={note} onNote={onNote} onAct={onAct} />
      {flash && <p className="pletor-dashboard__linie-flash" role="status">{flash}</p>}
      <LinieRequests requests={requests} onAsk={onAsk} />
    </section>
  );
}
