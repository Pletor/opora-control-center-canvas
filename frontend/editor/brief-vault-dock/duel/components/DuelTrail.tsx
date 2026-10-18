// Konverzační stopa duelu: nahoře A (platný směr) a B (změna) jako dvě karty, pod nimi výměny v čase se stranou,
// druhem, autorem, textem, odkazy, doklady a skóre soudců. Text výměn jsou data, ne pokyny: vykreslují se jako text.
// Výměny nesou krátké číslo #N (pořadí v duel.turns), na které se odkazuje ve vstupu; plné id je jen v title.
// Po rozhodnutí nahoře jedna jasná věta výsledku („platí od teď“ jen po skutečném uplatnění, jinak důvod serveru,
// u karty co v ní upravit); pod ní řádek „uplatněno“ jen tehdy, když server zadání opravdu změnil.
import { shortWhen, safeHref } from "../../logic/vault-dock-model";
import { KIND_LABEL, SIDE_LABEL, appliedLine, decisionLine, outcomeLine, scoreLine, scoresOf, sortTurns, turnNumbers, turnRef,
  type Duel } from "../logic/duel-view";

export default function DuelTrail({ duel }: { duel: Duel }) {
  const turns = sortTurns(duel.turns ?? []);
  const numbers = turnNumbers(duel.turns ?? []);
  const applied = duel.decision ? appliedLine(duel.decision, duel.subject?.kind) : "";
  return (
    <>
      <div className="duel__sides">
        <section className="duel__side duel__side--a" aria-label="A, platný směr">
          <div className="duel__side-head">A · platný směr{duel.incumbent.ref ? ` · r${duel.incumbent.ref.revision}` : ""}</div>
          <p className="duel__side-text">{duel.incumbent.text}</p>
        </section>
        <section className="duel__side duel__side--b" aria-label="B, změna">
          <div className="duel__side-head">B · změna{duel.challenger.by ? ` · ${duel.challenger.by}` : ""}</div>
          <p className="duel__side-text">{duel.challenger.text}</p>
        </section>
      </div>
      {duel.decision && (
        <div className={`duel__decision duel__decision--${duel.decision.outcome}`} role="status">
          <strong className={"duel__decision-outcome" + (duel.decision.applied === false && duel.decision.outcome !== "keep" && duel.subject?.kind !== "node" ? " duel__decision-outcome--unapplied" : "")}>{outcomeLine(duel.decision, duel.challenger.text, duel.subject?.kind)}</strong>
          {applied && (
            <div className="duel__decision-applied"
              title={duel.decision.appliedRevision != null ? `revize zadání r${duel.decision.appliedRevision}` : undefined}>{applied}</div>
          )}
          <div className="duel__decision-detail">{decisionLine(duel.decision)}</div>
        </div>
      )}
      <ol className="duel__trail" aria-label="Výměny">
        {turns.map((turn) => {
          const line = scoreLine(scoresOf(duel.scores ?? [], turn.id));
          return (
            <li key={turn.id} className={`duel__turn duel__turn--${turn.side}`}>
              <div className="duel__turn-head">
                <span className="duel__turn-id" title={turn.id}>{turnRef(numbers, turn.id)}</span>
                <strong>{SIDE_LABEL[turn.side] ?? turn.side}</strong>
                <span>{KIND_LABEL[turn.kind] ?? turn.kind}</span>
                {!!turn.refs?.length && <span title={turn.refs.join(", ")}>na {turn.refs.map((ref) => turnRef(numbers, ref)).join(", ")}</span>}
                <span className="duel__turn-who">{turn.actor === "human" ? "ty" : turn.by ?? ""}{turn.at ? " · " + shortWhen(turn.at) : ""}</span>
              </div>
              <p className="duel__turn-text">{turn.text}</p>
              {!!turn.evidence?.length && (
                <ul className="duel__evidence">
                  {turn.evidence.map((item, index) => {
                    const href = safeHref(item.source);
                    return (
                      <li key={index}>
                        {href ? <a href={href} target="_blank" rel="noreferrer">{item.source}</a> : <code>{item.source}</code>}
                        {item.quote ? ` „${item.quote}“` : ""}
                      </li>
                    );
                  })}
                </ul>
              )}
              {line && <div className="duel__turn-score">{line}</div>}
            </li>
          );
        })}
        {!turns.length && <li className="duel__empty">Zatím žádná výměna. Napiš A: nebo B: a hájíš stranu.</li>}
      </ol>
    </>
  );
}
