// Stůl = řádek karty: název (otevře kartu), stavová věta jako na kartě, pracovníci u stolu, nebo
// tlačítko „Posadit agenta“. Uzavřená karta tlačítko nemá.
import type { HireTarget } from "../logic/hire-message";
import type { Desk as DeskData } from "../logic/office-model";
import WorkerChip from "./WorkerChip";

type Props = {
  desk: DeskData;
  blocked: string | null;
  onOpenNode: (id: string) => void;
  onHire: (target: HireTarget) => void;
};

export default function Desk({ desk, blocked, onOpenNode, onHire }: Props) {
  const hireable = !desk.closed && !desk.workers.length;
  return (
    <li className={"office-desk" + (desk.closed ? " office-desk--closed" : "")}>
      <button type="button" className="office-desk__name" onClick={() => onOpenNode(desk.id)} title="Otevřít kartu">{desk.name}</button>
      <span className={"office-desk__state office-desk__state--" + desk.state.tone} title={desk.state.detail || desk.state.text}>{desk.state.text}</span>
      <span className="office-desk__seat">
        {desk.workers.map((w) => <WorkerChip key={w.id} worker={w} />)}
        {hireable && (
          <button type="button" className="office-desk__hire" disabled={!!blocked} title={blocked ?? "Poslat srdci zadání pro tuto kartu"}
            onClick={() => onHire({ kind: "node", id: desk.id, name: desk.name })}>
            Posadit agenta
          </button>
        )}
      </span>
    </li>
  );
}
