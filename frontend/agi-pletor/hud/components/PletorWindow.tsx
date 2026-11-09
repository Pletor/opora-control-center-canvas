import "../styles/pletor.css";
import { useEffect, useState } from "react";
import { usePletor } from "../logic/pletor-poll";
import { escalationText, heartText, type PletorMode } from "../logic/pletor-client";
import { HANDOFF_MS, REPLY_MS, hudLabel, hudState, hudWork } from "../logic/hud-state";
import { usePletorVoice } from "../logic/use-pletor-voice";
import PletorActions from "./PletorActions";
import PletorHeartLine from "./PletorHeartLine";
import PletorHeartPanel from "@/agi-pletor/hud-heart/components/PletorHeartPanel";
import PletorHud from "./PletorHud";
import PletorMessages from "./PletorMessages";
import PletorMicButton from "./PletorMicButton";
import PletorOrb from "./PletorOrb";
import PletorQuestionLine from "./PletorQuestionLine";
import PletorListener from "./PletorListener";
import PletorListenSwitch from "./PletorListenSwitch";
import PletorSettingsButton from "./PletorSettingsButton";
import PletorSettingsPanel from "./PletorSettingsPanel";
import PletorVoiceDraft from "./PletorVoiceDraft";

type Props = {
  mode: PletorMode; project: string; projectName: string; workspace: string; onMode: (mode: PletorMode) => void; onDashboard?: () => void;
  listening: boolean; onListening: (on: boolean, error?: string) => void; settings: boolean; onSettings: (open: boolean) => void;
};

/**
 * Rodič Pletora (docs/navrhy/2026-11-04-pletor-jarvis.md): hlasový Pletor nad srdcem projektu, bez psaní.
 * Drží stav konverzace a odesílá (`usePletor`) i hlas (`usePletorVoice`), takže obojí přežije přepnutí HUD ↔ okno.
 * Stav jádra odvodí jednou (hudState: přemýšlím / mluvím / srdce pracuje / poslouchám) pro HUD, okno i popup;
 * časovače po REPLY_MS a HANDOFF_MS vrátí záblesk odpovědi a předání srdci do klidu.
 * Režim drží App; „hud“ vykreslí kokpit (PletorHud), „window“ plovoucí okno, „closed“ nic a nic nenačítá.
 * Přepínač Poslech (`listening`) a otevřené nastavení (`settings`, ozubené kolo) drží App taky: zapnutý Poslech
 * trvale poslouchá i při zavřeném okně a mimo HUD ukazuje plovoucí popup PletorListener; nastavení skládá tady.
 */
export default function PletorWindow({ mode, project, projectName, workspace, onMode, onDashboard, listening, onListening, settings, onSettings }: Props) {
  const active = mode !== "closed" || listening || settings;
  const pletor = usePletor(active, project, workspace, mode !== "closed");
  const voice = usePletorVoice(pletor, active, { on: listening, onFail: (message) => onListening(false, message) });
  const [now, setNow] = useState(() => Date.now());
  const [log, setLog] = useState(true);
  useEffect(() => {
    if (pletor.repliedAt === null) return;
    setNow(Date.now());
    const timers = [REPLY_MS, HANDOFF_MS].map((ms) => setTimeout(() => setNow(Date.now()), ms));
    return () => timers.forEach(clearTimeout);
  }, [pletor.repliedAt]);
  const work = hudWork(pletor.heart, pletor.actions, pletor.repliedAt, now);
  // Hlasová odpověď se čte už z proudu: „přemýšlím“ trvá do prvního kousku odpovědi, pak mluví (a mikrofon ji smí utnout).
  const thinking = pletor.sending && voice.phase !== "speaking";
  const state = hudState({ sending: thinking, voice: voice.phase, error: !!pletor.failure, work, repliedAt: pletor.repliedAt, now });
  const label = hudLabel(state, work);
  const gear = (tone: "bar" | "dark") => <PletorSettingsButton tone={tone} open={settings} onToggle={() => onSettings(!settings)} />;
  const panel = settings && <PletorSettingsPanel voice={voice} brain={pletor.brain} onBrain={(brain, model, effort) => void pletor.setBrain(brain, model, effort)} onClose={() => onSettings(false)} />;
  const listener = listening && (
    <PletorListener state={state} label={label} level={voice.level} interim={voice.interim} messages={pletor.messages}
      error={pletor.failure || voice.error} onListening={(on) => onListening(on)} onInterrupt={voice.interrupt} onFullscreen={() => onMode("hud")}
      settings={gear("dark")} voiceListening={voice.phase === "listening"} manual={voice.prefs.endpointMs === 0} endpointMs={voice.prefs.endpointMs} onFinish={voice.finish} />
  );
  if (mode === "closed") return <>{listener}{panel}</>;
  const mic = <PletorMicButton phase={voice.phase} supported={voice.supported} blocked={voice.blocked} disabled={thinking || !project} onToggle={voice.toggle} />;
  const voiceError = voice.error && <p className="pletor-mic__error" role="alert">{voice.error}</p>;
  if (mode === "hud") {
    return (
      <>
        <PletorHud pletor={pletor} state={state} label={label} voice={voice} mic={mic} voiceError={voiceError} project={projectName}
          onWindow={() => onMode("window")} settingsOpen={settings}
          tools={<><PletorListenSwitch on={listening} onChange={(on) => onListening(on)} />{gear("dark")}{onDashboard && <button type="button" className="pletor-hud__button" onClick={onDashboard} title="Velín AGI Pletor">Velín</button>}</>} />
        {panel}
      </>
    );
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
        <PletorOrb state={state} />
        <p className={`pletor__state pletor__state--${state}`} role="status">{label}</p>
        <div className="pletor__controls">
          {mic}
          {gear("bar")}
          <button type="button" className="pletor__log-toggle" aria-expanded={log} onClick={() => setLog((open) => !open)}>Přepis</button>
        </div>
        {pletor.failure && <p className="pletor__failure" role="alert">{pletor.failure}</p>}
        {voiceError}
        <PletorVoiceDraft listening={voice.phase === "listening"} draft={voice.interim} manual={voice.prefs.endpointMs === 0} endpointMs={voice.prefs.endpointMs} onFinish={voice.finish} />
        <PletorHeartPanel status={pletor.heartStatus} answered={pletor.answered} place="window" />
        <PletorQuestionLine text={pletor.question} />
        {log && <PletorMessages messages={pletor.messages} sending={pletor.sending} />}
        <PletorActions actions={pletor.actions} />
      </aside>
      {panel}
    </>
  );
}
