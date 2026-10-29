import type { PanelSize } from "../logic/assistant-prefs";
import SizeSwitch from "./SizeSwitch";

/** Hlavička panelu: vlevo jméno kanálu, vpravo přepínač velikostí a křížek. */
export default function PanelHead({ size, onSize, onClose }: { size: PanelSize; onSize: (size: PanelSize) => void; onClose: () => void }) {
  return (
    <header className="assistant-panel__head">
      <span className="assistant-panel__brand">Srdce</span>
      <SizeSwitch size={size} onSize={onSize} />
      <button type="button" className="assistant-panel__close" aria-label="Zavřít asistenta" title="Zavřít asistenta" onClick={onClose}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
          <path d="M6 6l12 12M18 6 6 18" />
        </svg>
      </button>
    </header>
  );
}
