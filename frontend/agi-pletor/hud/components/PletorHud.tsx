import "../styles/pletor-hud.css";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { usePletor } from "../logic/pletor-poll";
import type { usePletorVoice } from "../logic/use-pletor-voice";
import { brainLabel, escalationText, heartText } from "../logic/pletor-client";
import type { HudState } from "../logic/hud-state";
import PletorHeartPanel from "@/agi-pletor/hud-heart/components/PletorHeartPanel";
import PletorActions from "./PletorActions";
import PletorHudBar from "./PletorHudBar";
import PletorHudCanvas from "./PletorHudCanvas";
import PletorHudCorners from "./PletorHudCorners";
import PletorMessages from "./PletorMessages";
import PletorQuestionLine from "./PletorQuestionLine";

type Props = {
  pletor: ReturnType<typeof usePletor>; state: HudState; label: string; voice: ReturnType<typeof usePletorVoice>;
  mic: ReactNode; voiceError: ReactNode; project: string; onWindow: () => void; tools: ReactNode; settingsOpen: boolean;
};

/**
 * Rodič režimu HUD (docs/navrhy/2026-11-04-pletor-jarvis.md): Pletor přes celou obrazovku jako nejvyšší vrstva.
 * Pletor je hlasový: uprostřed velké jádro, pod ním mikrofon (`mic`), vpravo tichý přepis rozhovoru ke čtení.
 * Stav jádra, mikrofon a nástroje lišty (Poslech, ozubené kolo) dostane hotové od PletorWindow.
 * Esc složí kokpit do okna; dialogy pod ním Esc nedostanou. Když hlas poslouchá nebo čte, Esc patří hlasu
 * (usePletorVoice ho utne), a když je otevřené nastavení, zavře se nastavení; kokpit v obou případech zůstane.
 */
export default function PletorHud({ pletor, state, label, voice, mic, voiceError, project, onWindow, tools, settingsOpen }: Props) {
  const [fps, setFps] = useState(0);
  const leave = useRef(onWindow);
  leave.current = onWindow;
  const keep = useRef(false);
  // Trvalý poslech (přepínač Poslech) Esc nebere; patří mu jen při čtení odpovědi.
  keep.current = settingsOpen || voice.phase === "speaking" || (voice.phase === "listening" && !voice.ambient);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.isComposing || keep.current) return;
      event.preventDefault();
      event.stopPropagation();
      leave.current();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, []);

  return (
    <div className="pletor-hud" role="region" aria-label="Pletor">
      <PletorHudBar heart={heartText(pletor.heart)} onEnter={onWindow}>{tools}</PletorHudBar>
      <div className="pletor-hud__main">
        <section className="pletor-hud__stage">
          <PletorHudCanvas state={state} level={voice.level} onFps={setFps} />
          <PletorHudCorners project={project} brain={brainLabel(pletor.brain)} state={state} label={label} escalations={pletor.escalations.length} fps={fps} />
          <PletorHeartPanel status={pletor.heartStatus} answered={pletor.answered} place="hud" />
        </section>
        <aside className="pletor-hud__console" aria-label="Přepis rozhovoru">
          <div className="pletor-hud__console-head">Přepis · {escalationText(pletor.escalations.length)}</div>
          <PletorQuestionLine text={pletor.question} />
          <PletorMessages messages={pletor.messages} sending={pletor.sending} />
          <PletorActions actions={pletor.actions} />
          {pletor.failure && <p className="pletor__failure" role="alert">{pletor.failure}</p>}
        </aside>
      </div>
      <div className="pletor-hud__command">
        {mic}
        {voiceError}
      </div>
    </div>
  );
}
