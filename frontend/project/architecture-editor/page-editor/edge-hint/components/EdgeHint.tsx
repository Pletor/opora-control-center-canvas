import type { EdgeHintText } from "../logic/edge-hint";
import "../styles/edge-hint.css";

type Props = { hint: EdgeHintText; x: number; y: number };

/** Malý popisek u kurzoru nad vazbou; rodič drží, která vazba je najetá, a kam kurzor ukazuje. */
export default function EdgeHint({ hint, x, y }: Props) {
  return <div className="edge-hint" role="tooltip" style={{ left: x, top: y }}>
    <span className="edge-hint__route">{hint.route}</span>
    <span className="edge-hint__kind">{hint.kind}</span>
  </div>;
}
