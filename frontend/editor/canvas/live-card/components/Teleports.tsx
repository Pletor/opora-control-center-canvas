import type { LiveEdge } from "../logic/live-card-types";
import { relationView, stateView } from "../logic/live-card-view";

/** Teleporty: vazby na karty jinde v mapě; klik otevře živou kartu na druhém konci. */
export default function Teleports({ edges, onOpenCard }: { edges: LiveEdge[]; onOpenCard: (nodeId: string) => void }) {
  if (!edges.length) return null;
  return <nav className="live-card__ports" aria-label="Teleporty">
    {edges.map(edge => {
      const relation = relationView(edge.relation, edge.dir), other = stateView(edge.other.state);
      return <button key={edge.edgeId} type="button" className={`live-card__port${relation.dashed ? " live-card__port--code" : ""}`}
        onClick={() => onOpenCard(edge.other.nodeId)} title={edge.last ?? undefined}>
        <span className={`live-card__port-rel live-card__tone--${relation.tone}`}>{relation.label} {relation.arrow}</span>
        <span className={`live-card__dot live-card__tone--${other.tone}`} aria-label={other.label} />
        {edge.other.title}
        {edge.carries && <span className="live-card__port-carries">{edge.carries}</span>}
      </button>;
    })}
  </nav>;
}
