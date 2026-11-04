import "../styles/pletor-hud.css";
import { useEffect, useRef, useState } from "react";
import type { usePletor } from "../logic/pletor-poll";
import { brainText, escalationText, heartText } from "../logic/pletor-client";
import type { PletorOrbMode } from "../logic/pletor-orb-mode";
import { hudState } from "../logic/hud-palette";
import PletorActions from "./PletorActions";
import PletorComposer from "./PletorComposer";
import PletorHudBar from "./PletorHudBar";
import PletorHudCanvas from "./PletorHudCanvas";
import PletorHudCorners from "./PletorHudCorners";
import PletorMessages from "./PletorMessages";

type Props = { pletor: ReturnType<typeof usePletor>; orb: PletorOrbMode; project: string; canSend: boolean; onWindow: () => void };

/**
 * Rodič režimu HUD (docs/navrhy/2026-11-04-pletor-jarvis.md): Pletor přes celou obrazovku jako nejvyšší vrstva.
 * Rozhovor a odesílání dostane hotové od PletorWindow; sám skládá lištu, plátno, rohy a konzoli.
 * Esc (mimo rozepsané pole) složí kokpit do okna; dialogy pod ním Esc nedostanou.
 */
export default function PletorHud({ pletor, orb, project, canSend, onWindow }: Props) {
  const state = hudState(orb);
  const [fps, setFps] = useState(0);
  const leave = useRef(onWindow);
  leave.current = onWindow;
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.isComposing) return;
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
          <PletorHudCanvas state={state} onFps={setFps} />
          <PletorHudCorners project={project} brain={brainText(pletor.brain)} state={state} escalations={pletor.escalations.length} fps={fps} />
        </section>
        <aside className="pletor-hud__console" aria-label="Konzole Pletora">
          <div className="pletor-hud__console-head">Protokol relace · {escalationText(pletor.escalations.length)}</div>
          <PletorMessages messages={pletor.messages} sending={pletor.sending} />
          <PletorActions actions={pletor.actions} />
          {pletor.failure && <p className="pletor__failure" role="alert">{pletor.failure}</p>}
        </aside>
      </div>
      <div className="pletor-hud__command">
        <PletorComposer disabled={pletor.sending || !canSend} onSend={pletor.send} />
      </div>
    </div>
  );
}
