// Pata karty: štítky (max 3 + „+N“) vlevo, nenulové počty vpravo.
import { footCounts, type CardView } from "@/editor/canvas/node-card/logic/card-model";

export default function CardFoot({ view, onTag }: { view: CardView; onTag?: (tag: string) => void }) {
  return (
    <div className="node-card__foot">
      <span className="node-card__tags" aria-label="Štítky uzlu">
        {view.tags.map((tag) => (
          <button
            key={tag}
            type="button"
            className="node-card__tag nodrag"
            title={`Filtrovat plátno podle štítku ${tag}`}
            onClick={(e) => {
              e.stopPropagation();
              onTag?.(tag);
            }}
          >
            {tag}
          </button>
        ))}
        {view.hiddenTags > 0 && <span className="node-card__tag node-card__tag--more">+{view.hiddenTags}</span>}
      </span>
      <span className="node-card__counts">
        {footCounts(view).map((item) => (
          <span key={item.label} className="node-card__count">
            <b className="node-card__count-value">{item.value}</b> {item.label}
          </span>
        ))}
      </span>
    </div>
  );
}
