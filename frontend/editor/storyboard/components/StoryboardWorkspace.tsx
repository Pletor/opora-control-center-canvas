// Mód plátna Storyboard (rodič): výběr karty prostoru a mřížka editoru. Vybraná karta je výběr aplikace (`selectedNode`),
// změna se hlásí `onOpenNode`; samotný storyboard načítá, drží a ukládá StoryboardEditor pro jednu kartu.
import { useCallback, useMemo, useState } from "react";
import { cardsForPicker } from "../logic/storyboard-layout";
import CardPicker from "./CardPicker";
import StoryboardEditor from "./StoryboardEditor";
import "../styles/storyboard.css";

type GraphLike = { nodes: { id: string; kind: string; name: string }[] };

export default function StoryboardWorkspace({ project, workspace, graph, selectedNode, readOnly, onOpenNode, onDraw }: {
  project: string;
  workspace: string;
  graph: GraphLike;
  selectedNode: string | null;
  readOnly: boolean;
  onOpenNode: (id: string) => void;
  onDraw: (nodeId: string) => void;
}) {
  const cards = useMemo(() => cardsForPicker(graph), [graph]);
  const [marks, setMarks] = useState<Record<string, boolean>>({});
  const mark = useCallback((id: string, has: boolean) => setMarks((old) => (old[id] === has ? old : { ...old, [id]: has })), []);
  const card = cards.find((c) => c.id === selectedNode) ?? null;
  const picker = <CardPicker cards={cards} value={card?.id ?? null} marks={marks} onChange={onOpenNode} />;
  return (
    <div className="storyboard">
      {card
        ? <StoryboardEditor key={card.id} project={project} workspace={workspace} nodeId={card.id} readOnly={readOnly} picker={picker} onMark={mark} onDraw={onDraw} />
        : <><div className="storyboard__bar">{picker}</div><p className="storyboard__empty">Vyberte kartu, ke které chcete psát storyboard.</p></>}
    </div>
  );
}
