// Osa storyboardu: markery momentů (doteky podlahy zvýrazněné), playhead, posuvník času a přehrávání.
// Dílek jen hlásí: skok na čas, výběr momentu, přidání momentu, spuštění a zastavení.
import type { Moment } from "../logic/storyboard-model";

export default function MomentTimeline({ moments, duration, t, selected, playing, readOnly, onSeek, onSelect, onPlay, onAdd }: {
  moments: Moment[];
  duration: number;
  t: number;
  selected: number;
  playing: boolean;
  readOnly: boolean;
  onSeek: (t: number) => void;
  onSelect: (index: number) => void;
  onPlay: (playing: boolean) => void;
  onAdd: () => void;
}) {
  const pct = (v: number) => (duration > 0 ? (v / duration) * 100 : 0) + "%";
  return (
    <div className="storyboard__timeline">
      <div className="storyboard__timeline-row">
        <button type="button" onClick={() => onPlay(!playing)} aria-label={playing ? "Zastavit" : "Přehrát"}>{playing ? "❚❚" : "▶"}</button>
        <span className="storyboard__time">{t.toFixed(2)} / {duration} s</span>
        <button type="button" disabled={readOnly} onClick={onAdd}>+ moment zde</button>
      </div>
      <div className="storyboard__track">
        {moments.map((m, i) => (
          <button key={i} type="button" title={`${m.t} s · ${m.title}`} aria-label={`Moment ${m.title} v ${m.t} s`}
            className={"storyboard__marker" + (i === selected ? " storyboard__marker--selected" : "") + (m.state.contact === true ? " storyboard__marker--contact" : "") + (m.comment ? " storyboard__marker--wish" : "")}
            style={{ left: pct(m.t) }} onClick={() => onSelect(i)} />
        ))}
        <span className="storyboard__playhead" style={{ left: pct(t) }} aria-hidden="true" />
      </div>
      <input type="range" min={0} max={duration} step={0.01} value={t} aria-label="Čas" onChange={(e) => onSeek(Number(e.target.value))} />
    </div>
  );
}
