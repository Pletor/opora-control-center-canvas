// Řádek karty v rozbaleném sektoru: název, stav práce, kuličky procesu a tichý počet podnětů. Klik otevře kartu.
import CardProcess from "@/editor/canvas/node-card/components/CardProcess";
import { workLabels } from "@/editor/canvas/node-card/components/WorkNow";
import "@/editor/canvas/node-card/styles/node-card.css";
import { cardBucket, type TowerCard } from "../logic/tower-model";

const ideasWord = (n: number) => (n === 1 ? "podnět" : n < 5 ? "podněty" : "podnětů");

export default function TowerCardRow({ card, onOpenNode }: { card: TowerCard; onOpenNode: (id: string) => void }) {
  const unknown = !card.statusKnown && !card.proposed;
  const label = card.proposed ? "ke schválení" : unknown ? "stav neznámý" : card.status === "idle" ? "v klidu" : workLabels[card.status];
  return (
    <li className={"tower-card" + (card.closed ? " tower-card--closed" : "")}>
      <button type="button" className="tower-card__open" onClick={() => onOpenNode(card.id)} title={card.purpose || card.name}>
        <span className="tower-card__name">{card.name}</span>
        <span className={"tower-card__status tower-card__status--" + (unknown ? "unknown" : cardBucket(card))}>{label}</span>
        {card.process && <span className="tower-card__process"><CardProcess view={card.process} detail="far" /></span>}
        {card.ideas > 0 && <span className="tower-card__ideas">{card.ideas} {ideasWord(card.ideas)}</span>}
      </button>
    </li>
  );
}
