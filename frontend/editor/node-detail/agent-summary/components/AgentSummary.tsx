// Souhrn práce agentů nad kapitolami módu Text (`docs/souhrn-prace-agentu.md`). Rodič dílku: skládá
// hlavičku, řadu filtrů, tabulku řádků a legendu. Řádky dostává hotové (jen rozbalené karty), sám jen
// filtruje a řadí čistými funkcemi; nic nenačítá ani neukládá. Filtr, řazení i hover drží TextWorkspace,
// protože hover a skok na kapitolu spojují souhrn s kapitolami pod ním.
import { useMemo } from "react";
import {
  SUMMARY_FILTERS, filterRows, pendingCount, sortRows, summaryHeadline,
  type SummaryFilter, type SummaryRow, type SummarySort,
} from "@/editor/node-detail/agent-summary/logic/agent-summary";
import AgentSummaryLegend from "@/editor/node-detail/agent-summary/components/AgentSummaryLegend";
import AgentSummaryRow from "@/editor/node-detail/agent-summary/components/AgentSummaryRow";
import Icon from "@/ui-kit/icon/components/Icon";
import "@/editor/node-detail/agent-summary/styles/agent-summary.css";

const COLUMNS = ["Karta", "Stav", "Paměť", "Komunikace", "Ověření", "Další krok", "Změna"];

export type AgentSummaryProps = {
  rows: SummaryRow[];
  expandedCount: number;
  totalCount: number;
  filter: SummaryFilter;
  sort: SummarySort;
  onFilter: (filter: SummaryFilter) => void;
  onSort: (sort: SummarySort) => void;
  onRefresh: () => void;
  hovered: string | null;
  onHover: (id: string | null) => void;
  onJump: (id: string) => void;
  now: Date;
};

export default function AgentSummary({
  rows, expandedCount, totalCount, filter, sort, onFilter, onSort, onRefresh, hovered, onHover, onJump, now,
}: AgentSummaryProps) {
  const visible = useMemo(() => sortRows(filterRows(rows, filter), sort), [rows, filter, sort]);
  const waiting = rows.filter((row) => pendingCount(row.entry?.overview ?? null) > 0).length;
  return (
    <section className="agent-summary" aria-label="Souhrn práce agentů" data-testid="agent-summary">
      <header className="agent-summary__head">
        <h3 className="agent-summary__title">Souhrn práce agentů</h3>
        <span className="agent-summary__headline">{summaryHeadline(expandedCount, waiting)}</span>
        <div className="agent-summary__tools">
          <button
            type="button"
            className={"agent-summary__tool" + (sort === "next" ? " agent-summary__tool--active" : "")}
            aria-pressed={sort === "next"}
            title="Přepnout pořadí: jak stojí na plátně, nebo co nejdřív potřebuje další krok"
            onClick={() => onSort(sort === "next" ? "canvas" : "next")}
          >
            <Icon name="arrow-up-down" size={16} />
            Řadit: {sort === "next" ? "další krok" : "plátno"}
          </button>
          <button type="button" className="agent-summary__tool" onClick={onRefresh} title="Znovu načíst souhrn paměti a briefy rozbalených karet">
            <Icon name="refresh-cw" size={16} />
            Obnovit
          </button>
        </div>
      </header>
      {rows.length === 0 ? (
        <div className="agent-summary__empty" data-testid="agent-summary-empty">
          <p className="agent-summary__empty-title">Zatím není co shrnout</p>
          <p className="agent-summary__empty-text">
            {totalCount > 0
              ? "Rozbal kapitolu karty níže šipkou u jejího názvu, nebo zmáčkni Rozbalit vše. Souhrn ukazuje jen rozbalené karty."
              : "Tahle vrstva zatím nemá žádné karty. Přidej uzel nebo sektor a jeho kapitola se objeví níže."}
          </p>
        </div>
      ) : (
        <>
          <div className="agent-summary__filters" role="group" aria-label="Filtr řádků souhrnu">
            <Icon name="filter" size={16} className="agent-summary__filters-icon" />
            {SUMMARY_FILTERS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={"agent-summary__filter" + (filter === item.key ? " agent-summary__filter--active" : "")}
                aria-pressed={filter === item.key}
                onClick={() => onFilter(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="agent-summary__scroll">
            <div className="agent-summary__table" role="table" aria-label="Rozbalené karty">
              <div className="agent-summary__row agent-summary__row--head" role="row">
                {COLUMNS.map((column) => (
                  <div key={column} role="columnheader" className={"agent-summary__cell agent-summary__cell--th" + (column === "Změna" ? " agent-summary__cell--change" : "")}>
                    {column}
                  </div>
                ))}
                <div role="columnheader" className="agent-summary__cell agent-summary__cell--th agent-summary__cell--lock">
                  <Icon name="lock" size={16} label="Zámek" />
                </div>
              </div>
              {visible.map((row) => (
                <AgentSummaryRow key={row.nodeId} row={row} now={now} hovered={hovered === row.nodeId} onHover={onHover} onJump={onJump} />
              ))}
            </div>
            {visible.length === 0 && <p className="agent-summary__no-match">Filtru nic neodpovídá.</p>}
          </div>
          <AgentSummaryLegend />
        </>
      )}
    </section>
  );
}
