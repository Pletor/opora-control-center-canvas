// Seznam duelů rozsahu: otevřené nahoře, u každého název, stav a nekalibrovanou sílu argumentů pro B („síla B 35 %“). Klik otevře konverzaci duelu (hlásí rodiči).
import { STRENGTH_HINT, percent, statusLabel, type DuelItem } from "../logic/duel-view";

export default function DuelList({ items, onOpen }: { items: DuelItem[]; onOpen: (id: string) => void }) {
  if (!items.length) return <p className="duel__empty">Žádný duel. Změnu směru otevřeš dole: „duel: co chceš změnit“.</p>;
  return (
    <ul className="duel__list" aria-label="Duely">
      {items.map((item) => (
        <li key={item.id}>
          <button type="button" className={"duel__list-item" + (item.open ? "" : " duel__list-item--decided")} onClick={() => onOpen(item.id)}>
            <span className="duel__list-title">{item.title}</span>
            <span className="duel__list-status">{statusLabel(item.status)}</span>
            <span className="duel__list-p" title={STRENGTH_HINT}>síla B {percent(item.p)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
