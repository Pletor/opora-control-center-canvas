import "../styles/pletor.css";
import { useEffect, useState } from "react";
import { usePletor } from "../logic/pletor-poll";
import { escalationText, heartText, type PletorMode } from "../logic/pletor-client";
import { REPLY_MS, orbMode } from "../logic/pletor-orb-mode";
import PletorActions from "./PletorActions";
import PletorComposer from "./PletorComposer";
import PletorHeartLine from "./PletorHeartLine";
import { usePletorVoice } from "../logic/use-pletor-voice";
import PletorHud from "./PletorHud";
import PletorMessages from "./PletorMessages";
import PletorMicButton from "./PletorMicButton";
import PletorOrb from "./PletorOrb";
import PletorVoiceToggles from "./PletorVoiceToggles";
import PletorListener from "./PletorListener";
import PletorListenSwitch from "./PletorListenSwitch";
import { hudState } from "../logic/hud-palette";

type Props = {
  mode: PletorMode; project: string; projectName: string; workspace: string; onMode: (mode: PletorMode) => void;
  listening: boolean; onListening: (on: boolean, error?: string) => void;
};

/**
 * Rodič Pletora (docs/navrhy/2026-11-04-pletor-jarvis.md, P1): jeden chat s Pletorem nad srdcem projektu.
 * Drží stav konverzace a odesílá (`usePletor`) i hlas (`usePletorVoice`, P3), takže obojí přežije přepnutí HUD ↔ okno.
 * Příkazový řádek s mikrofonem skládá jednou a dává ho oknu i kokpitu.
 * Odvozuje i stav jádra; jediný časovač po REPLY_MS vrátí záblesk odpovědi do dýchání.
 * Režim drží App; „hud“ vykreslí kokpit (PletorHud), „window“ plovoucí okno, „closed“ nic a nic nenačítá.
 * Přepínač Poslech (`listening`) drží App taky: zapnutý hlas trvale poslouchá i při zavřeném okně a mimo HUD
 * ukazuje plovoucí popup PletorListener; nepovolený mikrofon přepínač vrátí na false s hláškou.
 */
export default function PletorWindow({ mode, project, projectName, workspace, onMode, listening, onListening }: Props) {
  const active = mode !== "closed" || listening;
  const pletor = usePletor(active, project, workspace);
  const voice = usePletorVoice(pletor, active, { on: listening, onFail: (message) => onListening(false, message) });
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (pletor.repliedAt === null) return;
    setNow(Date.now());
    const timer = setTimeout(() => setNow(Date.now()), REPLY_MS);
    return () => clearTimeout(timer);
  }, [pletor.repliedAt]);
  const orb = orbMode({ sending: pletor.sending, error: !!pletor.failure, lastPletorAt: pletor.repliedAt, now });
  const listener = listening && (
    <PletorListener state={hudState(orb, voice.phase)} level={voice.level} interim={voice.interim} messages={pletor.messages}
      error={pletor.failure || voice.error} onListening={(on) => onListening(on)} onInterrupt={voice.interrupt} onFullscreen={() => onMode("hud")} />
  );
  if (mode === "closed") return listener || null;
  const disabled = pletor.sending || !project;
  // Psaná zpráva chce krátkou odpověď ke čtení jen se zapnutým Hlasem; hlasová posílá `voice` sama (usePletorVoice).
  const composer = (
    <PletorComposer disabled={disabled} interim={voice.ambient ? "" : voice.interim} onSend={(text) => pletor.send(text, voice.prefs.voice)}>
      <PletorMicButton phase={voice.phase} supported={voice.supported} blocked={voice.blocked} disabled={disabled} onToggle={voice.toggle} />
      <PletorVoiceToggles prefs={voice.prefs} canListen={voice.supported} voices={voice.voices} chosen={voice.chosen} onChange={voice.setPrefs} />
    </PletorComposer>
  );
  const voiceError = voice.error && <p className="pletor-mic__error" role="alert">{voice.error}</p>;
  if (mode === "hud") {
    return <PletorHud pletor={pletor} orb={orb} voice={voice} composer={composer} voiceError={voiceError} project={projectName} onWindow={() => onMode("window")}
      listenSwitch={<PletorListenSwitch on={listening} onChange={(on) => onListening(on)} />} />;
  }
  return (
    <>
      {listener}
      <aside className="pletor" aria-label="Pletor">
        <header className="pletor__head">
          <strong className="pletor__title">Pletor</strong>
          <button type="button" className="pletor__close" aria-label="Plná obrazovka" title="Plná obrazovka" onClick={() => onMode("hud")}>⛶</button>
          <button type="button" className="pletor__close" aria-label="Zavřít Pletora" title="Zavřít" onClick={() => onMode("closed")}>×</button>
        </header>
        <PletorHeartLine heart={heartText(pletor.heart)} escalations={escalationText(pletor.escalations.length)} />
        <PletorOrb mode={orb} />
        <PletorMessages messages={pletor.messages} sending={pletor.sending} />
        <PletorActions actions={pletor.actions} />
        {pletor.failure && <p className="pletor__failure" role="alert">{pletor.failure}</p>}
        {voiceError}
        {composer}
      </aside>
    </>
  );
}
