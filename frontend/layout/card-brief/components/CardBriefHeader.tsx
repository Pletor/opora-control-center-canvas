// Hlavička zadání: kdo je vybraná karta. Jméno na prvním řádku, pod ním tři tiché značky —
// druh (uzel / sektor / oblast) v barvě kategorie bloků, fáze v barvě kategorie agentů, stav
// otevřeno/uzavřeno neutrálně. Pod značkami stojí trvalá poznámka „Jen ke čtení“, zlatě jako
// ostatní upozornění v aplikaci — tenhle blok žádný model nespouští a nic nezapisuje.
// Dílek nic nenačítá; dostane hotová data z `briefSummary` a jen je vykreslí.
import type { BriefSummary } from "@/layout/card-brief/logic/card-brief-view";

export default function CardBriefHeader({ header }: { header: BriefSummary["header"] }) {
  return (
    <header className="card-brief__brief-head" data-testid="card-brief-head">
      <strong className="card-brief__brief-name">{header.name}</strong>
      <div className="card-brief__brief-meta">
        {header.kindLabel && (
          <span className="card-brief__brief-flag card-brief__brief-flag--kind">{header.kindLabel}</span>
        )}
        {header.phaseLabel && (
          <span className="card-brief__brief-flag card-brief__brief-flag--phase">{header.phaseLabel}</span>
        )}
        <span
          className={
            "card-brief__brief-flag " +
            (header.done ? "card-brief__brief-flag--done" : "card-brief__brief-flag--open")
          }
        >
          {header.done ? "uzavřeno" : "otevřeno"}
        </span>
      </div>
      <p className="card-brief__readonly">Jen ke čtení</p>
      {header.done && header.doneNote && <p className="card-brief__brief-note">{header.doneNote}</p>}
    </header>
  );
}
