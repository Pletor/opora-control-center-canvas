import type { CSSProperties, RefObject } from "react";
import type { BoardLayout } from "../logic/linie-board";
import type { Labels } from "../logic/linie-labels";
import type { LayerState } from "../logic/linie-prefs";
import LinieNames from "./LinieNames";
import LiniePlot from "./LiniePlot";

type Props = {
  scrollRef: RefObject<HTMLDivElement | null>; names: number;
  layout: BoardLayout; selected: string; labels: Labels; lit: Set<string> | null; layers: LayerState;
  chips: Record<string, string>;
  onPick: (ticketId: string) => void;
  onRename: (rowId: string, name: string) => void;
  onFold: (rowId: string, collapsed: boolean) => void;
  onFocus: (branch: string) => void;
  onNames: (width: number) => void;
  onRenaming: (on: boolean) => void;
};

/**
 * Editor Linie jako jediný posuvný prvek: mřížka „názvy | plátno“, nahoře sticky časová hlavička, vlevo sticky sloupec
 * názvů. Kolečko, Shift+kolečko a tažení obsluhuje `useLinieZoom` nad `scrollRef`; tady se jen skládají dílky.
 */
export default function LinieBoard({ scrollRef, names, layout, selected, labels, lit, layers, chips, onPick, onRename, onFold, onFocus, onNames, onRenaming }: Props) {
  const selectedRow = layout.balls.find((ball) => ball.ticketId === selected)?.rowId ?? "";
  return (
    <div className="pletor-dashboard__linie-board" ref={scrollRef}>
      <div className="pletor-dashboard__linie-grid" style={{ "--linie-names": `${names}px`, "--linie-plot": `${layout.width}px` } as CSSProperties}>
        <LinieNames rows={layout.rows} chips={chips} selectedRow={selectedRow} onRename={onRename} onFold={onFold} onFocus={onFocus} onWidth={onNames} onRenaming={onRenaming} />
        <div className="pletor-dashboard__linie-ticks" aria-hidden="true">
          {layout.ticks.map((tick) => <span key={tick.x} className="pletor-dashboard__linie-tick" style={{ left: tick.x }}>{tick.text}</span>)}
        </div>
        <LiniePlot layout={layout} selected={selected} labels={labels} lit={lit} layers={layers} onPick={onPick} />
      </div>
    </div>
  );
}
