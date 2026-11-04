import "../styles/pletor-hud.css";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { usePletor } from "../logic/pletor-poll";
import type { usePletorVoice } from "../logic/use-pletor-voice";
import { brainText, escalationText, heartText } from "../logic/pletor-client";
import type { PletorOrbMode } from "../logic/pletor-orb-mode";
import { hudState } from "../logic/hud-palette";
import PletorActions from "./PletorActions";
import PletorHudBar from "./PletorHudBar";
import PletorHudCanvas from "./PletorHudCanvas";
import PletorHudCorners from "./PletorHudCorners";
import PletorMessages from "./PletorMessages";

type Props = {
  pletor: ReturnType<typeof usePletor>; orb: PletorOrbMode; voice: ReturnType<typeof usePletorVoice>;
  composer: ReactNode; voiceError: ReactNode; project: string; onWindow: () => void;
};

/**
 * Rodič režimu HUD (docs/navrhy/2026-11-04-pletor-jarvis.md): Pletor přes celou obrazovku jako nejvyšší vrstva.
 * Rozhovor a odesílání dostane hotové od PletorWindow; sám skládá lištu, plátno, rohy a konzoli.
 * Esc (mimo rozepsané pole) složí kokpit do okna; dialogy pod ním Esc nedostanou. Když hlas poslouchá nebo čte,
 * Esc patří hlasu (usePletorVoice ho utne) a kokpit zůstane. Příkazový řádek s mikrofonem skládá PletorWindow.
 */
export default function PletorHud({ pletor, orb, voice, composer, voiceError, project, onWindow }: Props) {
  const state = hudState(orb, voice.phase);
  const [fps, setFps] = useState(0);
  const leave = useRef(onWindow);
  leave.current = onWindow;
  const voiceBusy = useRef(false);
  voiceBusy.current = voice.phase !== "idle";
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.isComposing || voiceBusy.current) return;
      const active = document.activeElement;
      if ((active instanceof HTMLTextAreaElement || active instanceof HTMLInputElement) && active.value) return;
      event.preventDefault();
      event.stopPropagation();
      leave.current();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, []);

  return (
    <div className="pletor-hud" role="region" aria-label="Pletor">
      <PletorHudBar heart={heartText(pletor.heart)} onEnter={onWindow} />
      <div className="pletor-hud__main">
        <section className="pletor-hud__stage">
          <PletorHudCanvas state={state} level={voice.level} onFps={setFps} />
          <PletorHudCorners project={project} brain={brainText(pletor.brain)} state={state} escalations={pletor.escalations.length} fps={fps} />
        </section>
        <aside className="pletor-hud__console" aria-label="Konzole Pletora">
          <div className="pletor-hud__console-head">Protokol relace · {escalationText(pletor.escalations.length)}</div>
          <PletorMessages messages={pletor.messages} sending={pletor.sending} />
          <PletorActions actions={pletor.actions} />
          {pletor.failure && <p className="pletor__failure" role="alert">{pletor.failure}</p>}
          {voiceError}
        </aside>
      </div>
      <div className="pletor-hud__command">{composer}</div>
    </div>
  );
}
