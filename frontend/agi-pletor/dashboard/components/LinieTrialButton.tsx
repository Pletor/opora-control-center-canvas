import "../styles/pletor-dashboard-linie-trial.css";
import type { TrialButton } from "../logic/linie-trial";

type Props = { button: TrialButton; url: string; busy?: boolean; onStart: () => void; onTried: () => void };

/**
 * Tlačítko Vyzkoušet (docs/navrhy/2026-11-08-linie-zkouska.md §3, §6): běžící náhled otevře jako odkaz do nové karty
 * a zároveň nahlásí zkoušku; bez náhledu ho spustí; při stavbě je zamčené. Detail i řádek fronty kreslí totéž.
 */
export default function LinieTrialButton({ button, url, busy, onStart, onTried }: Props) {
  return (
    <span className="linie-trial__act">
      {button.kind === "open"
        ? <a className="linie-trial__go" href={url} target="_blank" rel="noreferrer" onClick={onTried}>{button.label} ↗</a>
        : <button type="button" className="linie-trial__go" disabled={!button.enabled || busy} title={button.why || undefined} onClick={onStart}>{busy ? "Probíhá…" : button.label}</button>}
      {button.note && <span className="linie-trial__note">{button.note}</span>}
    </span>
  );
}
