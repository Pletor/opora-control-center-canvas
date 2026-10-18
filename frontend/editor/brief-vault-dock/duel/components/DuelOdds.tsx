// Ukazatel síly argumentů pro B (nekalibrovaná heuristika ze skóre soudců, ne pravděpodobnost) vedle stopy: pruh s prahy 40 % a 75 %, počet hodnocených výměn, kdo je na tahu, kola
// a rozpad příspěvků s důvodem, aby šlo výsledek obhájit. Pod tím trend představy slovně. Jen zobrazení.
// Rozhodnutý duel neukazuje „směřuje k“ ze zóny P, ale pravdivé shrnutí z decision (oddsVerdict).
// „Na tahu“ říká rovnou, co napsat; výměny jsou krátká čísla #N jako ve stopě, plné id je v title.
import { ADOPT_AT, KEEP_AT, STRENGTH_HINT, STRENGTH_LABEL, contributionRows, oddsVerdict, onTurnLines, percent, roundsLabel, trendLine, turnNumbers, turnRef, zoneOf,
  type DuelResponse } from "../logic/duel-view";

export default function DuelOdds({ data }: { data: DuelResponse }) {
  const { probability, duel } = data;
  const p = probability?.p ?? 0;
  const n = probability?.n ?? 0;
  const zone = zoneOf(p, n);
  const numbers = turnNumbers(duel.turns ?? []);
  return (
    <aside className="duel__odds" aria-label="Síla argumentů">
      <div className="duel__odds-head">
        <span title={STRENGTH_HINT}>{STRENGTH_LABEL}</span>
        <strong className={`duel__odds-p duel__odds-p--${zone}`}>{percent(probability?.p)}</strong>
      </div>
      <div className="duel__meter" role="img" aria-label={`${STRENGTH_LABEL} ${percent(probability?.p)}, prahy 40 % a 75 %`}>
        <div className={`duel__meter-fill duel__meter-fill--${zone}`} style={{ width: `${Math.round(p * 100)}%` }} />
        <div className="duel__meter-mark" style={{ left: `${KEEP_AT * 100}%` }} />
        <div className="duel__meter-mark" style={{ left: `${ADOPT_AT * 100}%` }} />
      </div>
      <div className="duel__odds-line">n {n} hodnocených · {oddsVerdict(duel, zone)}</div>
      {onTurnLines(data.onTurn ?? [], duel.status, numbers, data.canDecide).map((line) => (
        <div key={line} className="duel__odds-line duel__odds-line--turn">{line}</div>
      ))}
      {data.rounds && <div className="duel__odds-line">{roundsLabel(data.rounds)}</div>}
      {!!probability?.contributions?.length && (
        <ol className="duel__contributions" aria-label="Rozpad příspěvků">
          {contributionRows(probability.contributions).map((item) => (
            <li key={item.turnId + item.kind} className="duel__contribution">
              <span className={`duel__contribution-delta duel__contribution-delta--${item.delta >= 0 ? "b" : "a"}`}>{item.deltaText}</span>
              <span><span title={item.turnId}>{turnRef(numbers, item.turnId)}</span> {item.side} · síla {item.strength} · váha {item.weight}</span>
              {item.reason && <span className="duel__contribution-reason">{item.reason}</span>}
            </li>
          ))}
        </ol>
      )}
      <div className="duel__odds-line duel__odds-line--trend">{trendLine(data.trajectory)}</div>
    </aside>
  );
}
