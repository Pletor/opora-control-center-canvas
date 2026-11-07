import type { CSSProperties, RefObject } from "react";
import type { BoardLayout } from "../logic/linie-board";
import type { LayerState } from "../logic/linie-prefs";
import { xOf } from "../logic/linie-zoom";
import LinieNames from "./LinieNames";
import LiniePlot from "./LiniePlot";

type Props = {
  scrollRef: RefObject<HTMLDivElement | null>; names: number;
  layout: BoardLayout; selected: string; lit: Set<string> | null; layers: LayerState;
  chips: Record<string, string>; corner: string;
  onPick: (ticketId: string) => void;
  onPickCommit: (ticketId: string, sha: string) => void;
  onRename: (rowId: string, name: string) => void;
  onFold: (rowId: string, collapsed: boolean) => void;
  onFocus: (branch: string) => void;
  onNames: (width: number) => void;
  onRenaming: (on: boolean) => void;
};

/**
 * Editor Linie jako jediný posuvný prvek: mřížka „názvy | plátno“, nahoře sticky časová hlavička se značkou „teď“,
 * vlevo sticky sloupec názvů. Kolečko, Shift+kolečko a tažení obsluhuje `useLinieZoom` nad `scrollRef`; tady se jen
 * skládají dílky.
 */
export default function LinieBoard({ scrollRef, names, layout, selected, lit, layers, chips, corner, onPick, onPickCommit, onRename, onFold, onFocus, onNames, onRenaming }: Props) {
  const selectedRow = layout.balls.find((ball) => ball.ticketId === selected)?.rowId ?? "";
  const nowX = layout.now === null ? null : xOf({ t0: layout.t0, k: layout.k }, layout.now);
  return (
    <div className="pletor-dashboard__linie-board" ref={scrollRef}>
      <div className="pletor-dashboard__linie-grid" style={{ "--linie-names": `${names}px`, "--linie-plot": `${layout.width}px` } as CSSProperties}>
        <LinieNames rows={layout.rows} lanes={layout.lanes} chips={chips} selectedRow={selectedRow} corner={corner} onRename={onRename} onFold={onFold} onFocus={onFocus} onWidth={onNames} onRenaming={onRenaming} />
        <div className="pletor-dashboard__linie-ticks" aria-hidden="true">
          {layout.ticks.map((tick) => <span key={tick.x} className="pletor-dashboard__linie-tick" style={{ left: tick.x }}>{tick.text}</span>)}
          {nowX !== null && <span className="pletor-dashboard__linie-nowtag" style={{ left: nowX }}>teď</span>}
        </div>
        <LiniePlot layout={layout} selected={selected} lit={lit} layers={layers} onPick={onPick} onPickCommit={onPickCommit} />
      </div>
    </div>
  );
}
