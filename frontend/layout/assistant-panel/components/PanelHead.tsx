import type { PanelChannel, PanelSize } from "../logic/assistant-prefs";
import type { TaskView } from "../logic/task-overview";
import ChannelSwitch from "./ChannelSwitch";
import SizeSwitch from "./SizeSwitch";

/**
 * Hlavička panelu: vlevo přepínač kanálu Srdce | Asistent (u Asistenta na celé ploše i „/ název úkolu
 * · model“, protože sloupec úkolů je daleko vlevo a oko potřebuje vědět, kde je), vpravo přepínač
 * velikostí a křížek.
 */
export default function PanelHead({ size, task, channel, onChannel, onSize, onClose }: { size: PanelSize; task: TaskView | null; channel: PanelChannel; onChannel: (channel: PanelChannel) => void; onSize: (size: PanelSize) => void; onClose: () => void }) {
  return (
    <header className="assistant-panel__head">
      <span className="assistant-panel__brand">
        <ChannelSwitch channel={channel} onChannel={onChannel} />
        {channel === "assistant" && size === "full" && task && (
          <>
            <span className="assistant-panel__brand-sep" aria-hidden="true">/</span>
            <span className="assistant-panel__brand-task">{task.title}</span>
            <span className="assistant-panel__brand-meta">· {task.model}</span>
          </>
        )}
      </span>
      <SizeSwitch size={size} onSize={onSize} />
      <button type="button" className="assistant-panel__close" aria-label="Zavřít asistenta" title="Zavřít asistenta" onClick={onClose}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
          <path d="M6 6l12 12M18 6 6 18" />
        </svg>
      </button>
    </header>
  );
}
