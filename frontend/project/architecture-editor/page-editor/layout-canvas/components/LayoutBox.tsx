import type { PointerEvent, ReactNode } from "react";
import type { SectionBox } from "@/shared/types/logic/types";
import { SECTION_ROLE_LABELS } from "../../../domain-site/logic/page-site";
import { czechCount } from "../logic/czech-count";
import type { BoxBadges } from "../logic/box-badges";
import type { LayoutSection } from "../logic/layout-grid";

export type BoxMode = "move" | "resize";
type Props = {
  section: LayoutSection; box: SectionBox; layer: "layout" | "logic"; badges: BoxBadges; dragging: boolean; selected: boolean;
  /** Box bez vnořených boxů: jen ten má místo na text (vnořená mřížka začíná hned pod hlavičkou). */
  leaf: boolean;
  /** Náhled (sken): bez cílů puštění, test id a ovládání, aby tah z palety nemířil do cizího layoutu. */
  preview: boolean;
  /** Vrstva Logika: štítky prvků, které se vejdou (`chipsInHead` = v řádku hlavičky, pod ní by přetekly přes vnořené boxy),
   * a názvy těch, které se nevešly (ukáže je „+N“); vnořené boxy jsou `children` (mřížka rodiče). */
  chips: ReactNode; chipsInHead: boolean; hidden: string[]; children: ReactNode;
  disabled: boolean;
  onBegin: (mode: BoxMode, event: PointerEvent<HTMLElement>) => void; onSelect: () => void;
  /** Dvojklik: zanořený pohled boxu (skica, vnořené boxy, Detail boxu). */
  onOpen: () => void; onRemove: () => void;
};

/** Jeden box layoutu v barvě role: název, role, značky (skica, inspirace, logika, Ověřeno), ✕ a úchyt velikosti; v Layoutu
 * funkčnost boxu (pohled Design kreslí `../design-page/`). Nic nepřeteče: dlouhý text
 * končí výpustkou a celý je v titulku. Klik mimo
 * tlačítka a štítky box vybere, dvojklik ho otevře v zanořeném pohledu (vnořený box vyhraje nad rodičem v obou případech).
 * Přejmenování je v Detailu boxu. */
export default function LayoutBox({ section, box, layer, leaf, badges, dragging, selected, preview, chips, chipsInHead, hidden, children, disabled, onBegin, onSelect, onOpen, onRemove }: Props) {
  const own = (target: EventTarget) => !(target as Element).closest("button, input, .layout-canvas__chip");
  const layout = layer === "layout";
  const text = !layout || !leaf || box.h < 2 ? "" : section.intent;
  const edit = layout && !disabled && !preview;
  const chipRow = !layout && <span className={"layout-canvas__box-chips" + (chipsInHead ? " layout-canvas__box-chips--head" : "")}>{chips}
    {hidden.length > 0 && <span className="layout-canvas__more" title={hidden.join(", ")}>+{hidden.length}</span>}</span>;
  return <div className={`layout-canvas__box layout-canvas__box--${section.role}` + (dragging ? " layout-canvas__box--dragging" : "") + (edit ? " layout-canvas__box--movable" : "")
      + (badges.proposed ? " layout-canvas__box--proposed" : "") + (selected ? " layout-canvas__box--selected" : "")}
    style={{ gridColumn: `${box.x + 1} / span ${box.w}`, gridRow: `${box.y + 1} / span ${box.h}` }}
    data-testid={preview ? undefined : "architecture-box-" + section.id} data-drop-section={layout || preview ? undefined : section.id}
    onPointerDown={edit ? (event) => onBegin("move", event) : undefined}
    onClick={preview ? undefined : (event) => { event.stopPropagation(); if (own(event.target)) onSelect(); }}
    onDoubleClick={preview ? undefined : (event) => { event.stopPropagation(); if (own(event.target)) onOpen(); }}
    title={[section.intent, preview ? "" : "Dvojklikem otevřete box"].filter(Boolean).join("\n") || undefined}>
    <div className="layout-canvas__box-head">
      <span className="layout-canvas__box-name" title={section.name}>{section.name}</span>
      <span className="layout-canvas__box-role">{SECTION_ROLE_LABELS[section.role]}</span>
      {chipsInHead && chipRow}
      <span className="layout-canvas__box-badges">
        {badges.proposed && <span className="layout-canvas__badge layout-canvas__badge--proposed">Návrh</span>}
        {badges.sketch && <span className="layout-canvas__badge" title="Box má skicu" aria-label="Skica">✎</span>}
        {badges.inspirations > 0 && <span className="layout-canvas__badge" title="Inspirace">🖼 {badges.inspirations}</span>}
        {layout && badges.logic > 0 && <span className="layout-canvas__badge">{czechCount(badges.logic, ["prvek", "prvky", "prvků"])}{badges.worst && ` · ${badges.worst}`}</span>}
        {badges.verified && <span className="layout-canvas__badge layout-canvas__badge--verified">Ověřeno</span>}
      </span>
      {edit && <button type="button" className="layout-canvas__box-remove" aria-label={`Odebrat ${section.name}`} data-testid={"architecture-box-remove-" + section.id} onClick={onRemove}>✕</button>}
    </div>
    {text && <p className="layout-canvas__box-text" title={text}>{text}</p>}
    {!chipsInHead && chipRow}
    {children}
    {edit && <span className="layout-canvas__box-resize" aria-hidden="true" onPointerDown={(event) => onBegin("resize", event)}/>}
  </div>;
}
