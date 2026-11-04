import "../styles/pletor.css";
import { useEffect, useState } from "react";
import { usePletor } from "../logic/pletor-poll";
import { escalationText, heartText } from "../logic/pletor-client";
import { REPLY_MS, orbMode } from "../logic/pletor-orb-mode";
import PletorActions from "./PletorActions";
import PletorComposer from "./PletorComposer";
import PletorHeartLine from "./PletorHeartLine";
import PletorMessages from "./PletorMessages";
import PletorOrb from "./PletorOrb";

/**
 * Rodič okna Pletor (docs/navrhy/2026-11-04-pletor-jarvis.md, P1): jeden chat s Pletorem nad srdcem projektu.
 * Drží stav konverzace a odesílá (`usePletor`); dílky dostanou hotová data a hlásí jen odeslání.
 * Odvozuje i stav jádra (PletorOrb); jediný časovač po REPLY_MS vrátí záblesk odpovědi do dýchání.
 * Zavřené okno nic nevykreslí a nic nenačítá.
 */
export default function PletorWindow({ open, project, workspace, onClose }: { open: boolean; project: string; workspace: string; onClose: () => void }) {
  const pletor = usePletor(open, project, workspace);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (pletor.repliedAt === null) return;
    setNow(Date.now());
    const timer = setTimeout(() => setNow(Date.now()), REPLY_MS);
    return () => clearTimeout(timer);
  }, [pletor.repliedAt]);
  if (!open) return null;
  const mode = orbMode({ sending: pletor.sending, error: !!pletor.failure, lastPletorAt: pletor.repliedAt, now });
  return (
    <aside className="pletor" aria-label="Pletor">
      <header className="pletor__head">
        <strong className="pletor__title">Pletor</strong>
        <button type="button" className="pletor__close" aria-label="Zavřít Pletora" title="Zavřít" onClick={onClose}>×</button>
      </header>
      <PletorHeartLine heart={heartText(pletor.heart)} escalations={escalationText(pletor.escalations.length)} />
      <PletorOrb mode={mode} />
      <PletorMessages messages={pletor.messages} sending={pletor.sending} />
      <PletorActions actions={pletor.actions} />
      {pletor.failure && <p className="pletor__failure" role="alert">{pletor.failure}</p>}
      <PletorComposer disabled={pletor.sending || !project} onSend={pletor.send} />
    </aside>
  );
}
