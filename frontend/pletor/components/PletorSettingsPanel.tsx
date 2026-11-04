import "../styles/pletor-settings.css";
import { useEffect, useRef, useState } from "react";
import type { PletorBrain } from "../logic/pletor-client";
import { readListenPrefs, writeListenPrefs } from "../logic/listen-prefs";
import type { usePletorVoice } from "../logic/use-pletor-voice";
import PletorListenSwitch from "./PletorListenSwitch";
import PletorSettingsVoices from "./PletorSettingsVoices";

type Props = {
  voice: ReturnType<typeof usePletorVoice>; brain: PletorBrain; onBrain: (brain: PletorBrain["brain"]) => void; onClose: () => void;
};

/**
 * Nastavení Pletora za ozubeným kolem: hlas (tabulka hlasů), přepínače čtení a poslechu a mozek (Claude / Ollama).
 * Volby se ukládají jako dosud jednou pro aplikaci (voice-prefs, listen-prefs); mozek přepíná server (`onBrain`).
 * Zavře ho Esc, klik mimo nebo znovu kolo; HUD mezitím Esc nebere (PletorHud `settingsOpen`).
 */
export default function PletorSettingsPanel({ voice, brain, onBrain, onClose }: Props) {
  const ref = useRef<HTMLElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  const [wakeOnly, setWakeOnly] = useState(() => readListenPrefs().wakeOnly);

  useEffect(() => {
    ref.current?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); close.current(); } };
    const onDown = (event: PointerEvent) => {
      const target = event.target as Element;
      if (!ref.current?.contains(target) && !target.closest?.("[data-pletor-settings-toggle]")) close.current();
    };
    window.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown, true);
    return () => { window.removeEventListener("keydown", onKey); document.removeEventListener("pointerdown", onDown, true); };
  }, []);

  // Poloha popupu se ukládá zvlášť (PletorListener); tady se mění jen „jen na oslovení“.
  const saveWake = (on: boolean) => { setWakeOnly(on); writeListenPrefs({ ...readListenPrefs(), wakeOnly: on }); };
  const local = brain.brain === "ollama" ? brain.model : brain.available[0] ?? null;

  return (
    <section ref={ref} className="pletor-settings" role="dialog" aria-label="Nastavení Pletora" tabIndex={-1}>
      <header className="pletor-settings__head">
        <strong className="pletor-settings__title">Nastavení Pletora</strong>
        <button type="button" className="pletor-settings__close" aria-label="Zavřít nastavení" onClick={onClose}>×</button>
      </header>

      <h3 className="pletor-settings__section">Mozek</h3>
      <div className="pletor-settings__brains" role="group" aria-label="Mozek Pletora">
        <button type="button" className="pletor-settings__brain" aria-pressed={brain.brain === "claude"} onClick={() => onBrain("claude")}>
          Claude (předplatné)
        </button>
        <button type="button" className="pletor-settings__brain" aria-pressed={brain.brain === "ollama"} disabled={!local}
          title={local ? undefined : "Ollama nenabízí žádný model"} onClick={() => onBrain("ollama")}>
          Lokální (Ollama · {local ?? "bez modelu"})
        </button>
      </div>

      <h3 className="pletor-settings__section">Čtení a poslech</h3>
      <div className="pletor-settings__switches">
        <PletorListenSwitch tone="small" label="Hlas" title="Odpovědi čte nahlas i na psané zprávy" on={voice.prefs.voice}
          onChange={(on) => voice.setPrefs({ voice: on })} />
        {voice.supported && (
          <PletorListenSwitch tone="small" label="Konverzace" title="Po odpovědi Pletor znovu poslouchá" on={voice.prefs.conversation}
            onChange={(on) => voice.setPrefs({ conversation: on })} />
        )}
        <PletorListenSwitch tone="small" label="Jen na oslovení" title="Reaguje jen věta s oslovením Pletore / Jarvisi" on={wakeOnly} onChange={saveWake} />
      </div>

      <h3 className="pletor-settings__section">Hlas</h3>
      <PletorSettingsVoices voices={voice.voices} chosen={voice.chosen} onChoose={(id) => voice.setPrefs({ ttsVoice: id })} onTry={voice.tryVoice} />
    </section>
  );
}
