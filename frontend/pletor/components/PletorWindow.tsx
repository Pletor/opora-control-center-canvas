import "../styles/pletor.css";
import { useEffect, useState } from "react";
import { usePletor } from "../logic/pletor-poll";
import { escalationText, heartText, type PletorMode } from "../logic/pletor-client";
import { REPLY_MS, orbMode } from "../logic/pletor-orb-mode";
import PletorActions from "./PletorActions";
import PletorComposer from "./PletorComposer";
import PletorHeartLine from "./PletorHeartLine";
import PletorHud from "./PletorHud";
import PletorMessages from "./PletorMessages";
import PletorOrb from "./PletorOrb";

type Props = { mode: PletorMode; project: string; projectName: string; workspace: string; onMode: (mode: PletorMode) => void };

/**
 * Rodič Pletora (docs/navrhy/2026-11-04-pletor-jarvis.md, P1): jeden chat s Pletorem nad srdcem projektu.
 * Drží stav konverzace a odesílá (`usePletor`), takže rozhovor přežije přepnutí HUD ↔ okno.
 * Odvozuje i stav jádra; jediný časovač po REPLY_MS vrátí záblesk odpovědi do dýchání.
 * Režim drží App; „hud“ vykreslí kokpit (PletorHud), „window“ plovoucí okno, „closed“ nic a nic nenačítá.
 */
export default function PletorWindow({ mode, project, projectName, workspace, onMode }: Props) {
  const pletor = usePletor(mode !== "closed", project, workspace);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (pletor.repliedAt === null) return;
    setNow(Date.now());
    const timer = setTimeout(() => setNow(Date.now()), REPLY_MS);
    return () => clearTimeout(timer);
  }, [pletor.repliedAt]);
  if (mode === "closed") return null;
  const orb = orbMode({ sending: pletor.sending, error: !!pletor.failure, lastPletorAt: pletor.repliedAt, now });
  if (mode === "hud") return <PletorHud pletor={pletor} orb={orb} project={projectName} canSend={!!project} onWindow={() => onMode("window")} />;
  return (
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
      <PletorComposer disabled={pletor.sending || !project} onSend={pletor.send} />
    </aside>
  );
}
