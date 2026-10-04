import type { AssistantContext } from "../logic/assistant-api";
import { stepsWord } from "../logic/tool-steps";
import { SCOPE_LABEL } from "../logic/work-scope";
import { turnLabel, type Turn } from "../logic/turns";
import type { OutlineDecisions } from "../logic/use-task-outline";

const ENVIRONMENT = { project: "Projekt", editor: "Editor", live: "Live Run" } as const;

function deniedWord(count: number): string {
  if (count === 1) return "zamítnutý";
  return count >= 2 && count <= 4 ? "zamítnuté" : "zamítnutých";
}

/**
 * Osnova úkolu vpravo na celé ploše: s čím asistent pracuje (kontext ze zprávy), kudy rozhovor šel
 * (tahy, aktivní zvýrazněný), co je potřeba rozhodnout (otázky z poslední odpovědi) a kolik kroků to
 * stálo. Klik na tah nebo otázku jen hlásí kotvu nahoru; posun dělá rodič.
 */
export default function Outline({
  context,
  contextSent,
  turns,
  activeTurn,
  decisions,
  steps,
  onJump,
}: {
  context: AssistantContext;
  contextSent: boolean;
  turns: Turn[];
  activeTurn: string | null;
  decisions: OutlineDecisions | null;
  steps: { steps: number; denied: number } | null;
  onJump: (anchor: string) => void;
}) {
  const selected = context.selectedNodeIds;
  return (
    <aside className="assistant-panel__outline" aria-label="Osnova úkolu">
      <section className="assistant-panel__outline-section">
        <h3 className="assistant-panel__outline-label">Kontext</h3>
        <dl className="assistant-panel__outline-facts">
          <dt className="assistant-panel__outline-key">Projekt</dt>
          <dd className="assistant-panel__outline-value" title={context.projectId}>{context.projectId || "žádný"}</dd>
          <dt className="assistant-panel__outline-key">Prostředí</dt>
          <dd className="assistant-panel__outline-value">{ENVIRONMENT[context.environment]} · {context.workspace}</dd>
          <dt className="assistant-panel__outline-key">Vrstva</dt>
          <dd className="assistant-panel__outline-value" title={context.layerId ?? undefined}>{context.layerId ?? "hlavní plátno"}</dd>
          <dt className="assistant-panel__outline-key">Rozsah</dt>
          <dd className="assistant-panel__outline-value">{SCOPE_LABEL[context.scope ?? "board"]}</dd>
          <dt className="assistant-panel__outline-key">{selected.length > 1 ? "Vybrané karty" : "Vybraná karta"}</dt>
          <dd className="assistant-panel__outline-value" title={selected.join(", ") || undefined}>{selected.length ? selected.join(", ") : "nic"}</dd>
        </dl>
        <p className="assistant-panel__outline-note">{contextSent ? "Odesláno s poslední zprávou." : "Pošle se s další zprávou."}</p>
      </section>

      {turns.length > 0 && (
        <nav className="assistant-panel__outline-section" aria-label="Průběh úkolu">
          <h3 className="assistant-panel__outline-label">Průběh</h3>
          <ol className="assistant-panel__outline-list">
            {turns.map((turn) => (
              <li key={turn.anchor}>
                <button
                  type="button"
                  className={"assistant-panel__outline-link" + (turn.anchor === activeTurn ? " assistant-panel__outline-link--active" : "")}
                  aria-current={turn.anchor === activeTurn ? "location" : undefined}
                  title={turn.user?.text}
                  onClick={() => onJump(turn.anchor)}
                >
                  <span className="assistant-panel__outline-index">{turn.index}</span>
                  <span className="assistant-panel__outline-text">{turnLabel(turn)}</span>
                </button>
              </li>
            ))}
          </ol>
        </nav>
      )}

      {decisions && (
        <section className="assistant-panel__outline-section">
          <h3 className="assistant-panel__outline-label">Otázky k rozhodnutí · {decisions.questions.length}</h3>
          <ol className="assistant-panel__outline-list">
            {decisions.questions.map((q) => (
              <li key={q.id}>
                <button type="button" className="assistant-panel__outline-link" title={q.question} onClick={() => onJump(decisions.anchorOf(q.id))}>
                  <span className="assistant-panel__outline-index">{q.id}</span>
                  <span className="assistant-panel__outline-text">{(q.topic || q.question).replace(/[*`]/g, "")}</span>
                </button>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="assistant-panel__outline-section">
        <h3 className="assistant-panel__outline-label">Kroky</h3>
        <p className="assistant-panel__outline-note">
          {steps
            ? `${steps.steps} ${stepsWord(steps.steps)}, ${steps.denied} ${deniedWord(steps.denied)}`
            : "Historie z přepisu kroky neuvádí."}
          <br />
          Asistent jen čte a radí.
        </p>
      </section>
    </aside>
  );
}
