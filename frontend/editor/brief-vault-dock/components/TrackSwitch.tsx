// Přepínač stop nahoře ve Schránce: CX/UX/UI · Backend + DB · Nezařazené, v čipu počet kapitol stopy.
// Jen zobrazení; vybranou stopu drží rodič (BriefVaultDock) a volbu hlásí callbackem.
import { TRACK_VIEWS, type TrackView } from "../logic/vault-tracks";

export default function TrackSwitch({ track, counts, onTrack }: {
  track: TrackView;
  counts: Record<TrackView, number>;
  onTrack: (track: TrackView) => void;
}) {
  return (
    <div className="vault-dock__tracks" role="group" aria-label="Stopa schránky">
      {TRACK_VIEWS.map((item) => (
        <button key={item.id} type="button" className="vault-dock__track" aria-pressed={track === item.id}
          title={item.hint} data-testid={"vault-track-" + item.id} onClick={() => onTrack(item.id)}>
          {item.label}
          <span className="vault-dock__track-count">{counts[item.id]}</span>
        </button>
      ))}
    </div>
  );
}
