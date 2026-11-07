import "../styles/pletor-dashboard-linie-rows.css";
import { useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { LANE, ROW_OPEN, TYPE_LABEL, type LaidLane, type LaidRow } from "../logic/linie-board";
import { clampNames } from "../logic/linie-prefs";
import { splitRowName } from "../logic/linie-row-name";

type Props = {
  rows: LaidRow[]; lanes: LaidLane[]; chips: Record<string, string>; selectedRow: string; corner: string;
  onRename: (rowId: string, name: string) => void; onFold: (rowId: string, collapsed: boolean) => void; onFocus: (branch: string) => void;
  onWidth: (width: number) => void; onRenaming: (on: boolean) => void;
};

// Automatický řádek nese jen část jména za rodičem (feat/velin-linie-strom → „strom“): rodiče čte oko ze stromu.
const label = (row: LaidRow) => (row.auto && row.parent && row.branch.startsWith(`${row.parent}-`) ? row.branch.slice(row.parent.length + 1) : row.name || row.branch);
const renamable = (row: LaidRow) => !row.fixed && !row.git && !row.auto && row.type !== "plan";
const chip = (row: LaidRow) => (row.planned ? "plánováno · bez větve" : row.git ? "z gitu" : row.auto ? "z větve" : TYPE_LABEL[row.type]);
const PLAN_ROW = new Set(["dir", "plan"]);
const RowName = ({ text }: { text: string }) => {
  const { prefix, last } = splitRowName(text);
  return <>{prefix && <span className="pletor-dashboard__linie-row-prefix"><bdi dir="ltr">{prefix}</bdi></span>}<span className="pletor-dashboard__linie-row-last">{last}</span></>;
};

/**
 * Sticky sloupec názvů vlevo a roh nad ním (prototyp Linie v3): na ose řádku sbalení, tečka barvy (kosočtverec
 * u experimentu), jméno s výpustkou (celé v `title` a v detailu) a chip; při najetí nebo výběru místo chipu akce ⌖ a ✎.
 * Pod osou větev odkud → kam (jen u řádku s kuličkou) a ve výšce každého pruhu worktree „⌂ agent · stav“. Klik nic
 * nepřeskládá: zaměření je ⌖, přejmenování ✎ nebo F2. Úchyt v rohu mění šířku sloupce.
 */
export default function LinieNames({ rows, lanes, chips, selectedRow, corner, onRename, onFold, onFocus, onWidth, onRenaming }: Props) {
  const [editing, setEditing] = useState("");
  const [value, setValue] = useState("");
  const drag = useRef<{ x: number; w: number } | null>(null);
  const edit = (row: LaidRow | null) => { setEditing(row?.id ?? ""); setValue(row?.name ?? ""); onRenaming(!!row); };
  const commit = (row: LaidRow) => {
    edit(null);
    if (value.trim() && value.trim() !== row.name) onRename(row.id, value.trim());
  };
  const grip = {
    onPointerDown: (event: PointerEvent<HTMLSpanElement>) => {
      drag.current = { x: event.clientX, w: event.currentTarget.parentElement?.getBoundingClientRect().width ?? 0 };
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    onPointerMove: (event: PointerEvent<HTMLSpanElement>) => { if (drag.current) onWidth(clampNames(drag.current.w + event.clientX - drag.current.x)); },
    onPointerUp: () => { drag.current = null; },
  };

  return (
    <>
      <div className="pletor-dashboard__linie-corner">
        {corner}
        <span className="pletor-dashboard__linie-grip" role="separator" aria-orientation="vertical" aria-label="Šířka sloupce názvů" {...grip} />
      </div>
      <div className="pletor-dashboard__linie-names">
        {rows.map((row) => {
          const base = row.height - LANE * row.lanes;
          const style = { height: row.height, "--c": row.color, "--ind": `${row.ind}px`, "--axis": `${row.y - row.top}px` } as CSSProperties;
          return (
            <div key={row.id} className={`pletor-dashboard__linie-row${row.id === selectedRow ? " pletor-dashboard__linie-row--selected" : ""}${row.type === "dir" ? " pletor-dashboard__linie-row--header" : ""}`} style={style}>
              <div className="pletor-dashboard__linie-row-top">
                <button type="button" className="pletor-dashboard__linie-icon" aria-expanded={!row.collapsed} aria-label={`${row.collapsed ? "Rozbalit" : "Sbalit"} ${label(row)}`}
                  onClick={() => onFold(row.id, !row.collapsed)}>{row.collapsed ? "▸" : "▾"}</button>
                <span className={`pletor-dashboard__linie-swatch${row.type === "experiment" ? " pletor-dashboard__linie-swatch--exp" : PLAN_ROW.has(row.type) ? " pletor-dashboard__linie-swatch--plan" : ""}`} />
                {editing === row.id ? (
                  <input className="pletor-dashboard__linie-rename" aria-label="Nový název řádku" value={value} autoFocus onChange={(event) => setValue(event.target.value)}
                    onBlur={() => commit(row)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") commit(row);
                      // Esc zavře jen přejmenování; Linie ani Velín ho už nedostanou.
                      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); edit(null); }
                    }} />
                ) : (
                  <span className="pletor-dashboard__linie-row-name" title={row.branch || label(row)} tabIndex={renamable(row) ? 0 : undefined}
                    onKeyDown={renamable(row) ? (event) => { if (event.key === "F2") { event.preventDefault(); edit(row); } } : undefined}><RowName text={label(row)} /></span>
                )}
                <span className="pletor-dashboard__linie-chip">{row.collapsed && chips[row.id] ? chips[row.id] : chip(row)}</span>
                <span className="pletor-dashboard__linie-acts">
                  {row.branch && <button type="button" className="pletor-dashboard__linie-icon" title={`Zaměřit ${row.branch}`} aria-label={`Zaměřit ${label(row)}`} onClick={() => onFocus(row.branch)}>⌖</button>}
                  {renamable(row) && editing !== row.id && <button type="button" className="pletor-dashboard__linie-icon" title="Přejmenovat (F2)" aria-label={`Přejmenovat ${label(row)}`} onClick={() => edit(row)}>✎</button>}
                </span>
              </div>
              {!row.collapsed && base >= ROW_OPEN && (
                <div className={`pletor-dashboard__linie-meta${row.branch || row.fixed || PLAN_ROW.has(row.type) ? "" : " pletor-dashboard__linie-meta--none"}`} title={row.meta}>{row.meta}</div>
              )}
              {lanes.filter((lane) => lane.rowId === row.id).map((lane, index) => (
                <div key={index} className="pletor-dashboard__linie-lane-name" style={{ top: base + LANE * index + LANE / 2 }} title={`worktree agenta ${lane.agent} · ${lane.state}`}>⌂ <strong>{lane.agent}</strong> · {lane.state}</div>
              ))}
            </div>
          );
        })}
      </div>
    </>
  );
}
