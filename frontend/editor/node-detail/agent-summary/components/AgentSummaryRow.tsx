// Jeden řádek souhrnu = jedna rozbalená kapitola. Čte se zleva doprava jako věta: která karta, kdo na
// ní psal, kolik paměti má, co čeká, jestli ví, kam jde, co dál, kdy se naposled pohnula a jestli je
// zamčená. Levný souhrn (stav, paměť, změna) je vidět hned; komunikace, ověření a další krok až z
// briefu, do té doby poctivé „–“. Klik na název posune stránku na kapitolu, hover ji zvýrazní.
import { READ_ONLY_TEXT } from "@/editor/node-detail/agent-workspace/logic/agent-overview";
import {
  actorLabel, gapsLabel, isRowLocked, nextActionIcon, relativeTime,
  type OverviewEntry, type SummaryKind, type SummaryRow,
} from "@/editor/node-detail/agent-summary/logic/agent-summary";
import CommsChips from "@/editor/node-detail/agent-summary/components/CommsChips";
import MemoryDots from "@/editor/node-detail/agent-summary/components/MemoryDots";
import WorkChip from "@/editor/node-detail/agent-summary/components/WorkChip";
import Icon from "@/ui-kit/icon/components/Icon";
import "@/editor/node-detail/agent-summary/styles/agent-summary.css";

const KIND_LABEL: Record<SummaryKind, string> = { node: "uzel", sector: "sektor", area: "oblast" };

function Missing({ entry, title: given }: { entry: OverviewEntry | null; title?: string }) {
  const title = given ?? (entry?.status === "loading" ? "Načítám brief karty…"
    : entry?.status === "error" ? "Brief karty se nenačetl." : "Brief karty zatím není načtený.");
  return <span className={"agent-summary__missing" + (entry?.status === "loading" ? " agent-summary__missing--loading" : "")} title={title}>–</span>;
}

function Check({ word, present }: { word: string; present: boolean }) {
  return <span className={"agent-summary__check" + (present ? " agent-summary__check--present" : " agent-summary__check--missing")}>
    {word} {present ? "✓" : "–"}
  </span>;
}

export default function AgentSummaryRow({ row, now, hovered, onHover, onJump }: {
  row: SummaryRow;
  now: Date;
  hovered: boolean;
  onHover: (id: string | null) => void;
  onJump: (id: string) => void;
}) {
  const overview = row.entry?.overview ?? null;
  const locked = isRowLocked(row);
  const lockText = row.closed ? READ_ONLY_TEXT.closed : overview?.readOnlyReason ? READ_ONLY_TEXT[overview.readOnlyReason] : "";
  const change = <>
    <span className="agent-summary__time">{relativeTime(row.updatedAt, now)}</span>
    {row.updatedAt && <small className="agent-summary__sub">{actorLabel(row.by)}</small>}
  </>;
  const next = overview?.nextAction;
  return (
    <div
      role="row"
      className={"agent-summary__row" + (hovered ? " agent-summary__row--hovered" : "")}
      data-testid="agent-summary-row"
      data-row-id={row.nodeId}
      onMouseEnter={() => onHover(row.nodeId)}
      onMouseLeave={() => onHover(null)}
    >
      <div role="cell" className="agent-summary__cell agent-summary__cell--card">
        <button type="button" className="agent-summary__name" onClick={() => onJump(row.nodeId)} title="Posunout na kapitolu karty">
          <span className="agent-summary__kind">{KIND_LABEL[row.kind]}</span>
          <span className="agent-summary__name-text">{row.name}</span>
        </button>
        <span className="agent-summary__change-inline">{change}</span>
      </div>
      <div role="cell" className="agent-summary__cell"><WorkChip state={row.state} /></div>
      <div role="cell" className="agent-summary__cell"><MemoryDots filled={row.filled} showCount /></div>
      <div role="cell" className="agent-summary__cell">
        {overview ? <CommsChips communication={overview.communication} emptyLabel="nic" /> : <Missing entry={row.entry} />}
      </div>
      <div role="cell" className="agent-summary__cell agent-summary__cell--stack">
        {overview ? <>
          <span className="agent-summary__verify">
            <Check word="cíl" present={overview.verification.goal === "present"} />
            <Check word="hotovo" present={overview.verification.dod === "present"} />
          </span>
          <small className={"agent-summary__sub" + (overview.verification.gaps > 0 ? " agent-summary__sub--gaps" : "")}>
            {gapsLabel(overview.verification.gaps)}
          </small>
        </> : <Missing entry={row.entry} />}
      </div>
      <div role="cell" className="agent-summary__cell agent-summary__cell--next">
        {next && next.label ? <>
          <Icon name={nextActionIcon(next.kind)} size={16} className="agent-summary__next-icon" />
          <span className="agent-summary__next-label" title={next.label}>{next.label}</span>
        </> : <Missing entry={row.entry} title={overview ? "Brief další krok neuvádí." : undefined} />}
      </div>
      <div role="cell" className="agent-summary__cell agent-summary__cell--stack agent-summary__cell--change">{change}</div>
      <div role="cell" className="agent-summary__cell agent-summary__cell--lock">
        {locked && <span className="agent-summary__lock" title={lockText}><Icon name="lock" size={16} label={lockText} /></span>}
      </div>
    </div>
  );
}
