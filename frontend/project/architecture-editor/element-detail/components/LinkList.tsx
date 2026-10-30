import type { EdgeCarries } from "@/shared/types/logic/types";
import { EDGE_CARRIES } from "@/shared/types/logic/types";
import { CARRIES_LABEL, parseCarries } from "@/shared/edge-carries/logic/edge-carries";
import type { NodeLink } from "../logic/agent-context";
import { canRemoveEditorEdge } from "../../logic/editor-model";

type Props = {
  title: string;
  links: NodeLink[];
  empty: string;
  /** Klik na druhý konec přenese výběr; bez callbacku je řádek jen text (Studio, jen čtení). */
  onSelect?: (id: string) => void;
  /** Volba „Co po vazbě teče“ u vazby `next`; bez callbacku nebo se zámkem jen ke čtení. Ukládá rodič. */
  onCarries?: (edgeId: string, carries: EdgeCarries | null) => void;
  /** Odebrání nakreslené vazby (`next` / `flow`); bez callbacku tlačítko chybí. Ukládá rodič. */
  onRemove?: (edgeId: string) => void;
  disabled?: boolean;
};

/** Seznam vazeb jedním směrem: druhý konec a port; klik přenese výběr na druhý konec.
 *  U vazby `next` člověk vybere, co po ní teče (navigace, data, příkaz, událost, nebo neurčeno);
 *  nakreslenou vazbu `next` / `flow` jde jedním klikem odebrat (vrátí se novým tahem). */
export default function LinkList({ title, links, empty, onSelect, onCarries, onRemove, disabled = false }: Props) {
  return (
    <section className="element-detail__links" aria-label={title}>
      <h4 className="element-detail__subtitle">{title}</h4>
      {links.length ? (
        <ul className="element-detail__list">
          {links.map((link) => (
            <li key={link.edgeId} className="element-detail__link-row">
              {onSelect ? (
                <button type="button" className="element-detail__link" onClick={() => onSelect(link.otherId)}>
                  <span className="element-detail__link-name">{link.otherName}</span>
                  <span className="element-detail__port">{link.port}</span>
                </button>
              ) : (
                <span className="element-detail__link">
                  <span className="element-detail__link-name">{link.otherName}</span>
                  <span className="element-detail__port">{link.port}</span>
                </span>
              )}
              {link.port === "next" && onCarries ? (
                <label className="element-detail__carries">
                  <span className="element-detail__carries-label">Co po vazbě teče</span>
                  <select className="element-detail__carries-select" value={link.carries ?? ""} disabled={disabled}
                    onChange={(event) => onCarries(link.edgeId, parseCarries(event.target.value))}>
                    <option value="">neurčeno</option>
                    {EDGE_CARRIES.map((value) => <option key={value} value={value}>{CARRIES_LABEL[value]}</option>)}
                  </select>
                </label>
              ) : null}
              {onRemove && canRemoveEditorEdge(link) ? (
                <button type="button" className="element-detail__link-remove" disabled={disabled} onClick={() => onRemove(link.edgeId)}>
                  Odstranit vazbu
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="element-detail__muted">{empty}</p>
      )}
    </section>
  );
}
