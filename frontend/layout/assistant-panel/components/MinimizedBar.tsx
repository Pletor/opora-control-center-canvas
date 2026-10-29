import type { Ref } from "react";

/**
 * Minimalizovaný panel: malá lišta vpravo dole nad minimapou, aby kanál srdce zůstal po ruce a nepřekážel.
 * Klik ji rozbalí do poslední velikosti.
 */
export default function MinimizedBar({ barRef, onExpand, onClose }: { barRef: Ref<HTMLElement>; onExpand: () => void; onClose: () => void }) {
  return (
    <aside ref={barRef} className="assistant-panel__mini" aria-label="Asistent (minimalizovaný)">
      <button type="button" className="assistant-panel__mini-open" title="Rozbalit asistenta" onClick={onExpand}>
        <span className="assistant-panel__mini-text">
          <span className="assistant-panel__mini-title">Srdce</span>
          <span className="assistant-panel__mini-meta">kanál k srdci projektu</span>
        </span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true" className="assistant-panel__mini-chevron">
          <path d="m6 15 6-6 6 6" />
        </svg>
      </button>
      <button type="button" className="assistant-panel__mini-close" aria-label="Zavřít asistenta" title="Zavřít asistenta" onClick={onClose}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
          <path d="M6 6l12 12M18 6 6 18" />
        </svg>
      </button>
    </aside>
  );
}
