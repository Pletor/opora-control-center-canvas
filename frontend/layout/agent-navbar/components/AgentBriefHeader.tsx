// Hlavička zadání: kdo je vybraná karta. Jméno na prvním řádku, pod ním tři tiché značky —
// druh (uzel / sektor / oblast) v barvě kategorie bloků, fáze v barvě kategorie agentů, stav
// otevřeno/uzavřeno neutrálně. Pod značkami stojí trvalá poznámka „Jen ke čtení“, zlatě jako
// ostatní upozornění v aplikaci — tahle záložka žádný model nespouští a nic nezapisuje.
// Dílek nic nenačítá; dostane hotová data z `briefSummary` a jen je vykreslí.
import type { BriefSummary } from "@/layout/agent-navbar/logic/agent-brief-view";

export default function AgentBriefHeader({ header }: { header: BriefSummary["header"] }) {
  return (
    <header className="agent-navbar__brief-head" data-testid="agent-brief-head">
      <strong className="agent-navbar__brief-name">{header.name}</strong>
      <div className="agent-navbar__brief-meta">
        {header.kindLabel && (
          <span className="agent-navbar__brief-flag agent-navbar__brief-flag--kind">{header.kindLabel}</span>
        )}
        {header.phaseLabel && (
          <span className="agent-navbar__brief-flag agent-navbar__brief-flag--phase">{header.phaseLabel}</span>
        )}
        <span
          className={
            "agent-navbar__brief-flag " +
            (header.done ? "agent-navbar__brief-flag--done" : "agent-navbar__brief-flag--open")
          }
        >
          {header.done ? "uzavřeno" : "otevřeno"}
        </span>
      </div>
      <p className="agent-navbar__readonly">Jen ke čtení</p>
      {header.done && header.doneNote && <p className="agent-navbar__brief-note">{header.doneNote}</p>}
    </header>
  );
}
