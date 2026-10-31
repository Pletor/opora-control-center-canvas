// Tichá řádka „kdo · kdy · co“ pod stavovým řádkem a krátký záblesk obrysu karty, je-li změna mladší
// než 10 minut. Dostane hotovou `FaceChange`; klik jen ohlásí nahoru (rodič otevře záznam činnosti s filtrem karty).
import type { FaceChange } from "../logic/face-change";
import { changeWhen, isFresh } from "../logic/face-change";
import { useNow } from "../logic/use-now";

export default function FaceLastChange({ change, onOpen }: { change: FaceChange | null; onOpen?: () => void }) {
  const now = useNow(30_000, !!change);
  if (!change) return null;
  const when = changeWhen(change.at, new Date(now));
  const text = [change.who, when, change.what].filter(Boolean).join(" · ");
  return (
    <>
      {isFresh(change.at, now) && <span key={change.at} className="card-face__flash" aria-hidden="true" />}
      <button type="button" className={"card-face__change card-face__change--" + change.whoKind + " nodrag"}
        data-oh-last-change={change.at} data-oh-last-change-who={change.whoKind}
        title={`Poslední změna: ${text}. Otevřít záznam činnosti této karty`} onClick={(event) => { event.stopPropagation(); onOpen?.(); }}>
        {text}
      </button>
    </>
  );
}
