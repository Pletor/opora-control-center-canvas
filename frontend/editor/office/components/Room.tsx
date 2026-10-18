// Místnost = dlaždice sektoru: název, podstata na jeden řádek, pruh stavů karet, „Vstoupit“,
// společný stůl s pracovníky sektoru a stoly karet.
import type { HireTarget } from "../logic/hire-message";
import { TONE_ORDER, type Room as RoomData } from "../logic/office-model";
import Desk from "./Desk";
import WorkerChip from "./WorkerChip";

export type RoomActions = {
  /** Důvod, proč nejde posadit dalšího agenta (obsazeno), nebo `null`. */
  blocked: string | null;
  onEnterLayer: (id: string) => void;
  onOpenNode: (id: string) => void;
  onHire: (target: HireTarget) => void;
  onSelectSession: (id: string) => void;
};

const TONE_LABEL = { ok: "hotovo", run: "pracuje", warn: "čeká na tebe", fail: "selhalo", idle: "čeká" } as const;

export default function Room({ room, blocked, onEnterLayer, onOpenNode, onHire, onSelectSession }: { room: RoomData } & RoomActions) {
  const total = room.desks.length;
  return (
    <article className="office-room" aria-label={"Místnost " + room.name}>
      <header className="office-room__head">
        <h4 className="office-room__name">{room.name}</h4>
        <button type="button" className="office-room__enter" onClick={() => onEnterLayer(room.id)}>Vstoupit</button>
      </header>
      {room.purpose && <p className="office-room__purpose" title={room.purpose}>{room.purpose}</p>}
      <div className="office-room__bar" role="img" aria-label={TONE_ORDER.map((t) => `${room.tones[t]} ${TONE_LABEL[t]}`).join(", ")}>
        {total > 0 && TONE_ORDER.filter((t) => room.tones[t] > 0).map((t) => (
          <span key={t} className={"office-room__part office-room__part--" + t} style={{ ["--w" as string]: `${(room.tones[t] / total) * 100}%` }} />
        ))}
      </div>
      <div className="office-room__common">
        <span className="office-room__label">Společný stůl</span>
        {room.common.map((w) => <WorkerChip key={w.id} worker={w} onSelect={onSelectSession} />)}
        <button type="button" className="office-room__hire" disabled={!!blocked} title={blocked ?? "Založit relaci asistenta pro celý sektor"}
          onClick={() => onHire({ kind: "sector", id: room.id, name: room.name })}>
          Posadit agenta k sektoru
        </button>
      </div>
      {total > 0 ? (
        <ul className="office-room__desks">
          {room.desks.map((desk) => <Desk key={desk.id} desk={desk} blocked={blocked} onOpenNode={onOpenNode} onHire={onHire} onSelectSession={onSelectSession} />)}
        </ul>
      ) : <p className="office-room__empty">Místnost zatím nemá stoly (karty).</p>}
    </article>
  );
}
