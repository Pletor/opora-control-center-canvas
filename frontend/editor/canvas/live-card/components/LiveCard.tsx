import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useDrawerFocus } from "@/hub/oporahub-card-drawer/logic/use-drawer-focus";
import { useLiveCard } from "../logic/use-live-card";
import { workBody } from "../logic/card-work";
import { api } from "@/shared/types/logic/types";
import { scopeQuery } from "@/hub/oporahub-mirror/logic/hub-read";
import { failureText } from "@/agi-pletor/dashboard/logic/linie-work";
import CardHead, { type Side } from "./CardHead";
import HumanSide from "./HumanSide";
import AgentSide from "./AgentSide";
import CardFoot from "./CardFoot";
import "../styles/live-card.css";

type Props = {
  project: string; workspace: string; nodeId: string;
  onClose: () => void; onPanel: () => void; onOpenCard: (nodeId: string) => void;
  onAskHeart?: (text: string) => Promise<boolean>;
  /** Jen u uzlu s vnitřním plátnem (sektor, stránka, prvek). */
  onEnterCanvas?: () => void;
};

const TURN_MS = 200;
const reducedMotion = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/**
 * Živá karta na 3/4 obrazovky: plátno zůstane ztlumené za ní. Líc pro člověka, rub pro agenty; přepínač
 * vedle ✕ kartu otočí. Rodič drží data (`useLiveCard`) a stranu, dílky dostávají props a hlásí callbacky.
 */
export default function LiveCard({ project, workspace, nodeId, onClose, onPanel, onOpenCard, onAskHeart, onEnterCanvas }: Props) {
  const dialog = useRef<HTMLElement>(null);
  useDrawerFocus(dialog, onClose);
  const [side, setSide] = useState<Side>("human");
  const [turning, setTurning] = useState(false);
  const data = useLiveCard(project, workspace, nodeId, side === "agent");
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current); }, []);
  const turn = (to: Side) => {
    if (to === side || turning) return;
    if (reducedMotion()) { setSide(to); return; }
    setTurning(true);
    timer.current = window.setTimeout(() => { setSide(to); setTurning(false); }, TURN_MS);
  };
  const copy = (text: string) => { void navigator.clipboard?.writeText(text).catch(() => undefined); };
  const card = data.card;
  // Úkol Linie s `cardId`: po založení se karta znovu načte a sekce Linie se naplní.
  const work = (body: object) => api(`/api/pletor/linie/work?${scopeQuery({ project, workspace })}`, workBody(body, nodeId))
    .then(() => { data.reload(); return ""; }, (failure: unknown) => failureText(failure));
  return createPortal(<div className="live-card__shade" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="live-card-title" data-oh-view="live-card" data-oh-node-id={nodeId} data-oh-side={side}
      className={`live-card${side === "agent" ? " live-card--agent" : ""}${turning ? " live-card--turn" : ""}`}>
      <CardHead card={card} nodeId={nodeId} side={side} onSide={turn} onClose={onClose} />
      <div className="live-card__body">
        {data.error && <p className="live-card__alert" role="alert">{data.error}</p>}
        {!card && !data.error && <p className="live-card__muted">Načítám kartu…</p>}
        {side === "human" && card && <HumanSide card={card} recent={data.recent} onOpenCard={onOpenCard} />}
        {side === "agent" && <AgentSide nodeId={nodeId} mark={card?.linie?.mark ?? null} agent={card?.agent ?? null} souhrn={data.souhrn} tvar={data.tvar}
          briefError={data.briefError} raw={data.raw} onPanel={onPanel} onCopy={copy} />}
      </div>
      {side === "human" ? <CardFoot card={card} busy={data.busy} onPanel={onPanel} onRefresh={data.reload} onAskHeart={onAskHeart} onEnterCanvas={onEnterCanvas} onWork={work} />
        : <footer className="live-card__foot"><span className="live-card__src">rub karty = stejná data jako líc, jen strojově · každý řádek má adresu · zápis jen nástroji s rolí</span></footer>}
    </section>
  </div>, document.body);
}
