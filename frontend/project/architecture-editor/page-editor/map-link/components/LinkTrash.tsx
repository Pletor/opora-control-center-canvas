import { EdgeLabelRenderer } from "@xyflow/react";
import Icon from "@/ui-kit/icon/components/Icon";

type Props = {
  /** Bod na vazbě těsně za výstupním portem (souřadnice plátna): mezera u zdrojové karty, nikdy pod cizí kartou. */
  at: { x: number; y: number };
  /** Kurzor je na vazbě nebo na popelnici: popelnice se ukáže (klávesnice ji ukáže fokusem). */
  shown: boolean;
  onHover: (inside: boolean) => void;
  onRemove: () => void;
};

/** Popelnice nakreslené vazby: jedním klikem ji odstraní (bez dialogu, vazba jde vrátit). Leží ve vrstvě popisků
 * React Flow nad kartami u výstupního portu: střed vazby může běžet za cizí kartou, začátek vazby nikdy. */
export default function LinkTrash({ at, shown, onHover, onRemove }: Props) {
  return <EdgeLabelRenderer>
    <button type="button" className={"map-link__trash nodrag nopan" + (shown ? " map-link__trash--shown" : "")} title="Odstranit vazbu" aria-label="Odstranit vazbu"
      style={{ transform: `translate(-50%, -50%) translate(${at.x}px, ${at.y}px)` }}
      onMouseEnter={() => onHover(true)} onMouseLeave={() => onHover(false)}
      onClick={(event) => { event.stopPropagation(); onRemove(); }}>
      <Icon name="trash" size={16}/>
    </button>
  </EdgeLabelRenderer>;
}
