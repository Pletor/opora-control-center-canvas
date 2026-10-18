import type { FrontierItem } from "../logic/use-frontier";
const labels = { frontier: "◉ K převzetí", claimed: "● Převzato", blocked: "🔒 Blokováno", waiting: "◷ Čeká na člověka", closed: "✓ Uzavřeno" };
export default function CardFrontier({ item }: { item: FrontierItem }) {
  return <div className="node-card__frontier node-card__row">
    <strong className="node-card__row-title">{labels[item.status]}</strong>
    {item.claim && <div>{item.claim}</div>}
    {!!item.blockedBy?.length && <div>Blokuje: {item.blockedBy.map(b => b.name || b.id).join(", ")}</div>}
    {item.waitingOnHuman?.map(w => <div key={w.blockId}>{w.ask}</div>)}
  </div>;
}
