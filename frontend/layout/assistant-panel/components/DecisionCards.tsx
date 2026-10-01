import type { DecisionSet } from "../logic/decisions";
import { decisionAnchor } from "../logic/turns";
import Markdown, { MarkdownInline } from "./Markdown";

/**
 * Odpověď s otázkami ve tvaru grillingu: úvodní text, mřížka karet otázek a závěr. Karta má nahoře
 * číslo a téma, pod tím otázku a dole celé doporučení jako akcentní štítek. Každá karta má kotvu,
 * aby na ni osnova uměla posunout. Počet sloupců určuje šířka sloupce konverzace (CSS), ne dílek.
 */
export default function DecisionCards({ messageId, set }: { messageId: string; set: DecisionSet }) {
  return (
    <div className="assistant-panel__decisions">
      {set.intro && <Markdown text={set.intro} />}
      <ol className="assistant-panel__decision-grid" aria-label={`Otázky k rozhodnutí (${set.questions.length})`}>
        {set.questions.map((q) => (
          <li key={q.id} id={decisionAnchor(messageId, q.id)} className="assistant-panel__decision">
            <span className="assistant-panel__decision-head">
              <span className="assistant-panel__decision-id">{q.id}</span>
              {q.topic && <span className="assistant-panel__decision-topic"><MarkdownInline text={q.topic} /></span>}
            </span>
            {q.question && (
              <div className="assistant-panel__decision-question">
                <Markdown text={q.question} compact />
              </div>
            )}
            {q.recommendation && (
              <p className="assistant-panel__decision-recommendation">
                <span className="assistant-panel__decision-label">Doporučení</span>
                <span className="assistant-panel__decision-tag"><MarkdownInline text={q.recommendation} /></span>
              </p>
            )}
          </li>
        ))}
      </ol>
      {set.outro && <Markdown text={set.outro} />}
    </div>
  );
}
