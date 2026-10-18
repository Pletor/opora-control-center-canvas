// Oblast na plátně: dashovaný rámeček, ne karta uzlu — beze bloků, jen jméno ve štítku a dva úchyty
// toku (in/out). Rodič (Board) dodá hotová data přes props; velikost nese `style` samotného React
// Flow uzlu (nastavuje Board z `data.view.w/h`), tenhle dílek jen kreslí rámeček a tahadlo změny
// velikosti. Přejmenování a změna velikosti bublají nahoru přes kontext akcí plátna (`renameNode`,
// `resizeArea`); data nenesou funkce, aby šla oblast při přestavbě znovu použít beze změny.
import { memo, useEffect, useRef, useState } from "react";
import { Handle, NodeResizer, Position, type Node, type NodeProps } from "@xyflow/react";
import { AREA_SIZE_MAX, AREA_SIZE_MIN, areaRollup } from "@/editor/canvas/area/logic/area-model";
import type { AreaColor } from "@/shared/types/logic/types";
import "@/editor/canvas/area/styles/area.css";
import { useCardActions } from "@/editor/canvas/node-card/logic/card-actions";
import AreaSummary from "@/editor/canvas/card-checklist/components/AreaSummary";
import type { areaSummary } from "@/editor/canvas/card-checklist/logic/card-checklist";

export type AreaCardView = { label: string; unnamed: boolean; members: number; w: number; h: number; color: AreaColor;
  /** Záměr oblasti (`node.purpose`): 2–5 vět od člověka, na rámečku nejvýš dva řádky. */
  purpose: string;
  /** Kolik členů oblasti je sektor (`kind === "sector"`). */
  sectors: number;
  /** Kolik členů oblasti je uzavřených (`done.confirmed`). */
  closed: number;
  /** Souhrn kontrolních pásů karet v oblasti (pipeline, důkazy, předávky, čeká na člověka). */
  summary?: ReturnType<typeof areaSummary> };

export type AreaCardData = {
  view: AreaCardView;
  disabled: boolean;
};

const AreaCard = memo(function AreaCard({ id, data, selected }: NodeProps<Node<AreaCardData>>) {
  const { view, disabled } = data;
  const actions = useCardActions();
  const onRename = (name: string) => actions.renameNode(id, name);
  const onResize = (w: number, h: number) => actions.resizeArea(id, w, h);
  const [editing, setEditing] = useState(false);
  const nameField = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!editing) return;
    nameField.current?.focus();
    nameField.current?.select();
  }, [editing]);

  const commitName = (value: string) => {
    setEditing(false);
    const next = value.trim();
    if (next !== view.label && !(next === "" && view.unnamed)) onRename(next);
  };

  return (
    <div
      className={"area-card" + (selected ? " area-card--selected" : "")}
      data-testid={"area-card-" + id}
      data-color={view.color}
    >
      <NodeResizer
        isVisible={selected && !disabled}
        minWidth={AREA_SIZE_MIN}
        minHeight={AREA_SIZE_MIN}
        maxWidth={AREA_SIZE_MAX}
        maxHeight={AREA_SIZE_MAX}
        onResizeEnd={(_, params) => onResize(params.width, params.height)}
      />
      <Handle
        type="target"
        position={Position.Left}
        className="nodrag area-card__flow area-card__flow--in"
        data-testid={"area-flow-in-" + id}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="flow"
        className="nodrag area-card__flow area-card__flow--out"
        data-testid={"area-flow-out-" + id}
      />
      {editing ? (
        <input
          ref={nameField}
          className="nodrag area-card__tag-input"
          aria-label="Název oblasti"
          data-testid={"area-rename-" + id}
          defaultValue={view.unnamed ? "" : view.label}
          autoFocus
          maxLength={160}
          onFocus={(e) => e.currentTarget.select()}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.nativeEvent.isComposing) return;
            if (e.key === "Enter") commitName(e.currentTarget.value);
            if (e.key === "Escape") setEditing(false);
          }}
          onBlur={(e) => commitName(e.currentTarget.value)}
        />
      ) : (
        <div
          className={"area-card__tag" + (view.unnamed ? " area-card__tag--unnamed" : "")}
          title={disabled ? undefined : `Dvojklik přejmenuje oblast · ${view.members} ${view.members === 1 ? "karta" : view.members < 5 ? "karty" : "karet"}`}
          onDoubleClick={(e) => {
            e.stopPropagation();
            if (!disabled) setEditing(true);
          }}
        >
          {view.label}
        </div>
      )}
      <div className="area-card__head">
        {view.purpose.trim() && <p className="area-card__intent" title={view.purpose}>{view.purpose}</p>}
        <p className="area-card__rollup" data-testid={"area-rollup-" + id}>
          {areaRollup({ sectors: view.sectors, cards: view.members - view.sectors, closed: view.closed })}
        </p>
        {view.summary && <AreaSummary summary={view.summary} />}
      </div>
    </div>
  );
});

export default AreaCard;
