import type { VoicePhase } from "../logic/hud-palette";

type Props = { phase: VoicePhase; supported: boolean; blocked: boolean; disabled: boolean; onToggle: () => void };

/**
 * Mikrofon vedle pole: klik = poslouchej, druhý klik (nebo Esc) = stop; při čtení odpovědi ji klik utne a poslouchá.
 * Bez rozpoznávání řeči (Firefox) jen tichá značka s vysvětlením; zakázaný mikrofon tlačítko vypne.
 */
export default function PletorMicButton({ phase, supported, blocked, disabled, onToggle }: Props) {
  if (!supported) {
    return <span className="pletor-mic pletor-mic--none" title="Hlas tento prohlížeč neumí; použij Chrome nebo Edge.">bez hlasu</span>;
  }
  const listening = phase === "listening";
  const title = blocked ? "Mikrofon není povolený v prohlížeči" : listening ? "Poslouchám (klik nebo Esc = stop)" : "Mluvit s Pletorem";
  return (
    <button type="button" className={"pletor-mic" + (listening ? " pletor-mic--listening" : "")} aria-pressed={listening}
      aria-label={listening ? "Přestat poslouchat" : "Mluvit s Pletorem"} title={title}
      disabled={blocked || (disabled && !listening)} onClick={onToggle}>
      <svg className="pletor-mic__icon" viewBox="0 0 24 24" aria-hidden="true">
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
      </svg>
    </button>
  );
}
