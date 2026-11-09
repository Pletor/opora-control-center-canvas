import type { CardFace } from "@/editor/canvas/card-face/logic/card-face";
import type { CardView } from "../logic/card-model";
import { progressAxes } from "../logic/progress-axes";
export default function CardProgress({ view, face }: { view: CardView; face?: CardFace }) {
  return <div className="node-card__progress-axes" aria-label="Stav návrhu, realizace a ověření">
    <dl>{progressAxes(view, face).map(axis => <div key={axis.label} title={axis.detail}><dt>{axis.label}</dt><dd>{axis.value}</dd></div>)}</dl>
    {face && <p>{"Dal\u0161\u00ed krok: "}{face.steps.label}</p>}
    {face?.footer?.kind === "blocked" && <p>{"\u010cek\u00e1 na: "}{face.footer.text}</p>}
  </div>;
}
