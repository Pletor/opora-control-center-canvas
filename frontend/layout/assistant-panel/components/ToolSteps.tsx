import { useState } from "react";
import { stepsLabel, stepsState, type ToolItem } from "../logic/tool-steps";

const MARK = { running: "…", ok: "✓", error: "!" } as const;
const LABEL = { running: "běží", ok: "v pořádku", error: "chyba" } as const;

/**
 * Kroky nástrojů mezi odpověďmi: jeden tlumený řádek „3 kroky (Read, Grep, Skill)“, který se klikem
 * rozbalí na jednotlivé kroky se souhrnem a výsledkem. Chyba je vidět značkou a počtem, ale nekřičí.
 */
export default function ToolSteps({ tools }: { tools: ToolItem[] }) {
  const [open, setOpen] = useState(false);
  const { running, errors } = stepsState(tools);
  return (
    <div className={"assistant-panel__steps" + (open ? " assistant-panel__steps--open" : "")}>
      <button type="button" className="assistant-panel__steps-line" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true" className="assistant-panel__steps-chevron">
          <path d="m9 6 6 6-6 6" />
        </svg>
        <span className="assistant-panel__steps-label">{stepsLabel(tools)}</span>
        {running && <span className="assistant-panel__steps-running">běží</span>}
        {errors > 0 && <span className="assistant-panel__steps-errors">{errors === 1 ? "1 chyba" : `${errors} ${errors < 5 ? "chyby" : "chyb"}`}</span>}
      </button>
      {open && (
        <ol className="assistant-panel__steps-list">
          {tools.map((tool) => (
            <li key={tool.id} className={`assistant-panel__step assistant-panel__step--${tool.status}`}>
              <span className="assistant-panel__step-mark" role="img" aria-label={LABEL[tool.status]}>{MARK[tool.status]}</span>
              <span className="assistant-panel__step-name">{tool.name}</span>
              <span className="assistant-panel__step-summary">{tool.summary}</span>
              {tool.result && <pre className="assistant-panel__step-result">{tool.result}</pre>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
