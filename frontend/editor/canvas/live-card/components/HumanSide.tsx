import type { LiveCard, RecentItem } from "../logic/live-card-types";
import Teleports from "./Teleports";
import TruthsGrid from "./TruthsGrid";
import FlowOutput from "./FlowOutput";
import LinieTrends from "./LinieTrends";
import RunLog from "./RunLog";
import DecisionsChildren from "./DecisionsChildren";

/** Líc pro člověka: teleporty, čtyři pravdy, tok a výstup, Linie a trendy, živý běh, rozhodnutí, potomci. */
export default function HumanSide({ card, recent, onOpenCard }: { card: LiveCard; recent: RecentItem[]; onOpenCard: (nodeId: string) => void }) {
  return <>
    <Teleports edges={card.edges} onOpenCard={onOpenCard} />
    <TruthsGrid truths={card.truths} />
    <FlowOutput flow={card.flow} output={card.output} />
    <LinieTrends card={card} />
    <RunLog recent={recent} />
    <DecisionsChildren card={card} onOpenCard={onOpenCard} />
  </>;
}
