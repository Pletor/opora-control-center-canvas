import { useState, type PointerEvent } from "react";
import type { CanvasNode, SectionBox } from "@/shared/types/logic/types";
import type { CardState } from "../../../card-state/logic/card-state";
import { bottomOf, cellAt, childrenOf, columnPitch, COLUMNS, ROW_PITCH, subtreeIds, type LayoutSection, type Point } from "../logic/layout-grid";
import { moveBox, removeBox, resizeBox } from "../logic/layout-edit";
import { magnet } from "../logic/magnet";
import { chipFit } from "../logic/chip-fit";
import { gridAt } from "../logic/drop-target";
import type { PageLogic } from "../logic/page-logic";
import { boxBadges } from "../logic/box-badges";
import LayoutBox, { type BoxMode } from "./LayoutBox";
import LogicChip from "./LogicChip";
import DesignPage from "../../design-page/components/DesignPage";
import "../styles/layout-canvas.css";

type Props = {
  layer: "layout" | "logic"; sections: LayoutSection[]; logic: PageLogic;
  states: ReadonlyMap<string, CardState>; selectedId: string | null;
  /** `layoutDisabled` = zámek struktury (vrstva Layout), `logicDisabled` = zámek obsahu (vrstva Logika). */
  layoutDisabled: boolean; logicDisabled: boolean;
  onLayout: (sections: LayoutSection[]) => void;
  onSelect: (id: string) => void; onRemoveElement: (id: string) => void; onCarry: (node: CanvasNode, event: PointerEvent) => void;
  /** Vybraný box (Detail boxu) a klik na box; boxy se skicou (značka ✎). */
  selectedBox?: string | null; onSelectBox?: (id: string) => void; sketches?: ReadonlySet<string>;
  /** Dvojklik na box: zanořený pohled boxu; dvojklik na štítek prvku otevře jeho plátno logiky (kontext `project-flows`). */
  onOpenBox?: (id: string) => void;
  /** Náhled jen ke čtení (sken webu): bez cílů puštění, výběru a test id; vždy s vypnutým layoutem i logikou. */
  preview?: boolean;
  /** Pohled vrstvy Layout (výchozí `layout` = funkčnost boxů na mřížce); `design` kreslí stránku v celku (`../design-page/`)
   * z obrázků vzhledu boxů (id sekce → data URL), bez tahu. */
  look?: "layout" | "design"; covers?: ReadonlyMap<string, string>;
};
/** `held` = prvek, který zachytí ukazatel až při prvním pohybu (klik a dvojklik na box tak zůstanou obyčejné).
 * `box` = tažený box po magnetu (kreslí se v původní mřížce), `landing` = celý layout po puštění (stín dopadu a uhnutí sourozenců). */
type Drag = { id: string; mode: BoxMode; from: Point; colW: number; origin: SectionBox; box: SectionBox; grab: Point; held: HTMLElement; pointerId: number;
  captured: boolean; landing: LayoutSection[] | null; key: string;
  /** Layout, ze kterého se počítal `landing`; když se mezitím změnil (souběžný zápis), puštění ho spočítá znovu. */
  base: LayoutSection[] };

/** Plátno stránky: drátový model na 12sloupcové mřížce s mezerami. Vrstva Layout táhne, zvětšuje a vnořuje boxy s magnetem
 * a stínem dopadu; vrstva Logika ukazuje prvky v boxech a pruh Celá stránka. Náhled tahu drží lokálně, změnu hlásí jednou při puštění. */
export default function LayoutCanvas(props: Props) {
  const { layer, sections, logic, layoutDisabled, preview = false } = props;
  const [drag, setDrag] = useState<Drag | null>(null);
  const chips = (nodes: CanvasNode[]) => nodes.map((node) => <LogicChip key={node.id} node={node} state={props.states.get(node.id)} selected={node.id === props.selectedId}
    disabled={props.logicDisabled} onSelect={props.onSelect} onRemove={props.onRemoveElement} onCarry={props.onCarry}/>);
  function begin(section: LayoutSection, mode: BoxMode, event: PointerEvent<HTMLElement>) {
    if (event.button !== 0 || (mode === "move" && (event.target as Element).closest("button, input"))) return;
    event.stopPropagation();
    const box = mode === "resize" ? event.currentTarget.parentElement : event.currentTarget;
    const rect = box?.parentElement?.getBoundingClientRect();
    if (!rect) return;
    const cell = cellAt(rect, { x: event.clientX, y: event.clientY });
    setDrag({ id: section.id, mode, from: { x: event.clientX, y: event.clientY }, colW: columnPitch(rect.width) || 1, origin: section.box, box: section.box,
      grab: { x: cell.x - section.box.x, y: cell.y - section.box.y }, held: event.currentTarget, pointerId: event.pointerId, captured: false, landing: null, key: "", base: sections });
  }
  /** Layout po puštění: stejné funkce jako zápis, aby stín ukázal přesně to, co se uloží. Nad jinou mřížkou box vnoří. */
  function land(current: Drag, box: SectionBox, point: Point): LayoutSection[] {
    if (current.mode === "resize") return resizeBox(sections, current.id, box.w, box.h);
    const parent = sections.find((item) => item.id === current.id)?.parent ?? null;
    const target = gridAt(point, subtreeIds(sections, current.id));
    if (target && target.parent !== parent) {
      const cell = cellAt(target.rect, point);
      const next = moveBox(sections, current.id, target.parent, { ...box, x: cell.x - current.grab.x, y: cell.y - current.grab.y });
      if (next !== sections) return next;
    }
    return moveBox(sections, current.id, parent, box);
  }
  function move(event: PointerEvent) {
    if (!drag) return;
    if (!drag.captured && Math.hypot(event.clientX - drag.from.x, event.clientY - drag.from.y) < 4) return;
    if (!drag.captured) drag.held.setPointerCapture(drag.pointerId);
    const dx = (event.clientX - drag.from.x) / drag.colW, dy = (event.clientY - drag.from.y) / ROW_PITCH;
    const { origin } = drag;
    const parent = sections.find((item) => item.id === drag.id)?.parent ?? null;
    const siblings = childrenOf(sections, parent).filter((item) => item.id !== drag.id).map((item) => item.box);
    const box = drag.mode === "move" ? magnet({ ...origin, x: origin.x + dx, y: origin.y + dy }, siblings, "move")
      : magnet({ ...origin, w: Math.min(origin.w + dx, COLUMNS - origin.x), h: origin.h + dy }, siblings, "resize");
    const landing = land(drag, box, { x: event.clientX, y: event.clientY });
    const key = JSON.stringify(landing.map((item) => [item.parent, item.box]));
    if (!drag.captured || key !== drag.key || drag.base !== sections || JSON.stringify(box) !== JSON.stringify(drag.box)) setDrag({ ...drag, box, landing, key, base: sections, captured: true });
  }
  function finish(event: PointerEvent) {
    if (!drag) return;
    setDrag(null);
    if (!drag.captured || !sections.some((item) => item.id === drag.id)) return;
    const landing = drag.base === sections && drag.landing ? drag.landing : land(drag, drag.box, { x: event.clientX, y: event.clientY });
    const key = (list: LayoutSection[]) => JSON.stringify(list.map((item) => [item.parent, item.box]));
    if (key(landing) !== key(sections)) props.onLayout(landing);
  }
  // Během tahu ostatní boxy stojí tam, kam uhnou; tažený box zůstává ve své mřížce (přemístění by zrušilo zachycení ukazatele).
  const shown = new Map((drag?.captured && drag.landing ? drag.landing : sections).map((section) => [section.id, section]));
  const boxOf = (section: LayoutSection) => (shown.get(section.id) ?? section).box;
  const landed = drag?.captured ? shown.get(drag.id) : undefined;
  const grid = (parent: string | null, share: number) => {
    const kids = childrenOf(sections, parent);
    return <div className={"layout-canvas__grid" + (parent ? " layout-canvas__grid--nested" : "")} data-grid-parent={preview ? undefined : parent ?? ""}
      style={parent ? undefined : { minHeight: Math.max(16, bottomOf(kids.map(boxOf)) + 4) * ROW_PITCH }}>
      {kids.map((section) => {
        const nodes = logic.byBox.get(section.id) ?? [];
        const box = drag?.id === section.id ? drag.box : boxOf(section);
        const leaf = !childrenOf(sections, section.id).length;
        const fit = chipFit(nodes.length, share * box.w / COLUMNS, box.h, leaf);
        return <LayoutBox key={section.id} section={section} box={box} layer={layer} leaf={leaf} chipsInHead={fit.head} hidden={nodes.slice(fit.shown).map((node) => node.name)}
          badges={boxBadges(section, nodes, props.states, !!props.sketches?.has(section.id))} selected={props.selectedBox === section.id} preview={preview}
          dragging={drag?.id === section.id && drag.captured} chips={chips(nodes.slice(0, fit.shown))} disabled={layoutDisabled}
          onBegin={(mode, event) => begin(section, mode, event)} onSelect={() => props.onSelectBox?.(section.id)} onOpen={() => props.onOpenBox?.(section.id)}
          onRemove={() => props.onLayout(removeBox(sections, section.id))}>{grid(section.id, share * box.w / COLUMNS)}</LayoutBox>;
      })}
      {landed && (landed.parent ?? null) === parent && <div className="layout-canvas__shadow" aria-hidden="true"
        style={{ gridColumn: `${landed.box.x + 1} / span ${landed.box.w}`, gridRow: `${landed.box.y + 1} / span ${landed.box.h}` }}/>}
    </div>;
  };
  if (layer === "layout" && props.look === "design") return <DesignPage sections={sections} covers={props.covers} selectedBox={props.selectedBox}
    onSelectBox={props.onSelectBox} onOpenBox={props.onOpenBox}/>;
  return <div className={"layout-canvas layout-canvas--" + layer} data-testid={preview ? undefined : "architecture-layout-canvas"} onPointerMove={move} onPointerUp={finish} onPointerCancel={() => setDrag(null)}>
    {layer === "logic" && <div className="layout-canvas__whole" data-drop-section="" data-testid="architecture-whole-page">
      <strong className="layout-canvas__whole-title">Celá stránka</strong>
      {chips(logic.whole)}
      {!logic.whole.length && <span className="layout-canvas__hint">Sem patří prvky celé stránky: kdo ji používá, kdo smí dovnitř, co musí splnit.</span>}
    </div>}
    <div className="layout-canvas__page">
      <div className="layout-canvas__guides" aria-hidden="true">{Array.from({ length: COLUMNS }, (_, index) => <span key={index}/>)}</div>
      {grid(null, 1)}
      {!sections.length && <p className="layout-canvas__empty">{layer === "layout"
        ? "Přetáhněte box z palety vlevo, nebo klikněte na šablonu."
        : "Stránka zatím nemá layout. Prvky logiky vložte na Celou stránku, nebo nejdřív poskládejte boxy ve vrstvě Layout."}</p>}
    </div>
  </div>;
}
