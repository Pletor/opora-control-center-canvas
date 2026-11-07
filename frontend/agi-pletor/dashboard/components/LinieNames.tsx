import { useRef, useState, type PointerEvent } from "react";
import { ROW_THIN, TYPE_LABEL, type LaidRow } from "../logic/linie-board";
import { clampNames } from "../logic/linie-prefs";

type Props = {
  rows: LaidRow[]; chips: Record<string, string>; selectedRow: string;
  onRename: (rowId: string, name: string) => void; onFold: (rowId: string, collapsed: boolean) => void; onFocus: (branch: string) => void;
  onWidth: (width: number) => void; onRenaming: (on: boolean) => void;
};

// Automatický řádek nese jen část jména za rodičem (feat/velin-linie-strom → „strom“): rodiče čte oko ze stromu.
const label = (row: LaidRow) => (row.auto && row.parent && row.branch.startsWith(`${row.parent}-`) ? row.branch.slice(row.parent.length + 1) : row.name || row.branch);
const renamable = (row: LaidRow) => !row.fixed && !row.git && !row.auto;
const chip = (row: LaidRow) => (row.planned ? "plánováno · bez větve" : row.git ? "z gitu" : row.auto ? "z větve" : TYPE_LABEL[row.type]);

/**
 * Sticky sloupec názvů vlevo a roh nad ním: jeden řádek textu s výpustkou (celé jméno v `title` a v detailu), pod ním
 * větev. Klik nic nepřeskládá: zaměření je tlačítko ⌖, přejmenování ✎ nebo F2. Úchyt v rohu mění šířku sloupce.
 */
export default function LinieNames({ rows, chips, selectedRow, onRename, onFold, onFocus, onWidth, onRenaming }: Props) {
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
        řádek · větev · cíl
        <span className="pletor-dashboard__linie-grip" role="separator" aria-orientation="vertical" aria-label="Šířka sloupce názvů" {...grip} />
      </div>
      <div className="pletor-dashboard__linie-names">
        {rows.map((row) => (
          <div key={row.id} className={`pletor-dashboard__linie-row pletor-dashboard__linie-row--depth-${Math.min(row.depth, 4)}${row.id === selectedRow ? " pletor-dashboard__linie-row--selected" : ""}`}
            style={{ height: row.height }}>
            <div className="pletor-dashboard__linie-row-top">
              <button type="button" className="pletor-dashboard__linie-icon" aria-expanded={!row.collapsed} aria-label={`${row.collapsed ? "Rozbalit" : "Sbalit"} ${label(row)}`}
                onClick={() => onFold(row.id, !row.collapsed)}>{row.collapsed ? "▸" : "▾"}</button>
              {editing === row.id ? (
                <input className="pletor-dashboard__linie-rename" aria-label="Nový název řádku" value={value} autoFocus onChange={(event) => setValue(event.target.value)}
                  onBlur={() => commit(row)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") commit(row);
                    // Esc zavře jen přejmenování; Linie ani Velín ho už nedostanou.
                    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); edit(null); }
                  }} />
              ) : (
                <span className="pletor-dashboard__linie-row-name" style={{ color: row.color }} title={label(row)} tabIndex={renamable(row) ? 0 : undefined}
                  onKeyDown={renamable(row) ? (event) => { if (event.key === "F2") { event.preventDefault(); edit(row); } } : undefined}>{label(row)}</span>
              )}
              {row.branch && <button type="button" className="pletor-dashboard__linie-icon" title={`Zaměřit ${row.branch}`} aria-label={`Zaměřit ${label(row)}`} onClick={() => onFocus(row.branch)}>⌖</button>}
              {renamable(row) && editing !== row.id && <button type="button" className="pletor-dashboard__linie-icon" title="Přejmenovat (F2)" aria-label={`Přejmenovat ${label(row)}`} onClick={() => edit(row)}>✎</button>}
              <span className="pletor-dashboard__linie-chip">{row.collapsed && chips[row.id] ? chips[row.id] : chip(row)}</span>
            </div>
            {row.height !== ROW_THIN && <div className={`pletor-dashboard__linie-meta${row.branch ? "" : " pletor-dashboard__linie-meta--none"}`} title={row.branchText}>{row.branchText}</div>}
            {!row.collapsed && row.height !== ROW_THIN && (
              <div className="pletor-dashboard__linie-meta">{row.fixed ? row.mappingText : `z ${row.parent || row.baseBranch || "—"} → cíl ${row.target || "zatím neurčeno"}`}</div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
