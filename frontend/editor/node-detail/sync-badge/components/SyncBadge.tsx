// Štítek verdiktu Oracle nad jedním uzlem: barva a věta řeknou hned, smí se to commitnout a smí to
// do mainu; další kroky stojí pod tím a sedm kontrol brány se schová za tlačítko. Data i callback
// pro rodiče nejsou potřeba — dílek jen zobrazuje hotový `view`, nic nenačítá ani neukládá.
import { useState } from "react";
import type { BadgeView } from "@/editor/node-detail/sync-badge/logic/sync-badge";
import "@/editor/node-detail/sync-badge/styles/sync-badge.css";

export default function SyncBadge({ view }: { view: BadgeView | null }) {
  const [expanded, setExpanded] = useState(false);
  if (!view) return null;
  return (
    <section className={`sync-badge sync-badge--${view.tone}`} aria-label="Verdikt Oracle" data-testid="sync-badge">
      <div className="sync-badge__head">
        <span className="sync-badge__dot" aria-hidden="true" />
        <span className="sync-badge__label">{view.label}</span>
      </div>
      <p className="sync-badge__detail">{view.detail}</p>
      {view.steps.length > 0 && (
        <ul className="sync-badge__steps">
          {view.steps.map((step) => (
            <li key={step} className="sync-badge__step">
              {step}
            </li>
          ))}
        </ul>
      )}
      {view.checks.length > 0 && (
        <>
          <button
            type="button"
            className="sync-badge__toggle"
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? "Skrýt kontroly" : "Zobrazit kontroly"}
          </button>
          {expanded && (
            <ul className="sync-badge__checks">
              {view.checks.map((check) => (
                <li
                  key={check.id}
                  className={"sync-badge__check" + (check.passed ? " sync-badge__check--passed" : " sync-badge__check--failed")}
                >
                  <span className="sync-badge__check-state">{check.passed ? "Prošla" : "Neprošla"}</span>
                  <span className="sync-badge__check-name">{check.name}</span>
                  {!check.passed && check.signal && <span className="sync-badge__check-signal">{check.signal}</span>}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
