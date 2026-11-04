import { SPEEDS } from "../logic/play-trace";
import type { PlayState } from "../logic/use-play";
import "../styles/flow-play.css";

type Props = { play: PlayState; canRun: boolean; onRun: () => void };

/** Ovládání přehrávání případu: Play / Pauza, krok zpět a vpřed, Restart, rychlost a Stop. Bez načtené trasy je jediné
 * tlačítko „Play“, které trasu vyžádá od serveru; chybu simulace říká větou vedle tlačítek, nic nepadá. */
export default function FlowPlayBar({ play, canRun, onRun }: Props) {
  const total = play.response?.trace.length ?? 0, loaded = !!play.response;
  return <div className="flow-play-bar" data-testid="flow-play-bar">
    {!loaded
      ? <button type="button" className="flow-play-bar__button flow-play-bar__button--primary" disabled={!canRun || play.loading} data-testid="flow-play-start" onClick={onRun}>{play.loading ? "Počítám…" : "▶ Play"}</button>
      : <>
        <button type="button" className="flow-play-bar__button" disabled={play.index === 0} aria-label="Krok zpět" data-testid="flow-play-back" onClick={play.back}>◀ Krok</button>
        {play.playing
          ? <button type="button" className="flow-play-bar__button flow-play-bar__button--primary" data-testid="flow-play-pause" onClick={play.pause}>❚❚ Pauza</button>
          : <button type="button" className="flow-play-bar__button flow-play-bar__button--primary" data-testid="flow-play-resume" onClick={play.play}>▶ Play</button>}
        <button type="button" className="flow-play-bar__button" disabled={play.index >= total - 1} aria-label="Krok vpřed" data-testid="flow-play-forward" onClick={play.forward}>Krok ▶</button>
        <button type="button" className="flow-play-bar__button" data-testid="flow-play-restart" onClick={play.restart}>↺ Restart</button>
        <span className="flow-play-bar__speeds" role="group" aria-label="Rychlost">
          {SPEEDS.map((speed) => <button key={speed} type="button" className={`flow-play-bar__button${play.speed === speed ? " flow-play-bar__button--on" : ""}`} aria-pressed={play.speed === speed}
            data-testid={`flow-play-speed-${speed}`} onClick={() => play.setSpeed(speed)}>{speed}×</button>)}
        </span>
        <span className="flow-play-bar__count" data-testid="flow-play-count">krok {play.index + 1} / {total}</span>
        <button type="button" className="flow-play-bar__button" data-testid="flow-play-stop" title="Skončit přehrávání a vrátit plátno do úprav" onClick={play.stop}>■ Stop</button>
      </>}
    {play.error && <span className="flow-play-bar__error" role="alert" data-testid="flow-play-error">{play.error}</span>}
  </div>;
}
