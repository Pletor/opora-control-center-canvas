import { useState } from "react";
import type { LiveCard } from "../logic/live-card-types";
import { clock } from "../logic/live-card-view";
import { workDraft } from "../logic/card-work";
import LinieWorkForm from "@/agi-pletor/dashboard/components/LinieWorkForm";

type Props = {
  card: LiveCard | null; busy: boolean; onPanel: () => void; onRefresh: () => void;
  /** Zpráva srdci přes kanál člověka (App `answerHeart`); bez Editoru chybí a tlačítko se nekreslí. */
  onAskHeart?: (text: string) => Promise<boolean>;
  onEnterCanvas?: () => void;
  /** Založí úkol Linie navázaný na kartu (formulář Velína); vrací chybu, nebo "" při úspěchu. */
  onWork: (body: object) => Promise<string>;
};

/** Patička líce: další krok a poslední zásah srdce; tlačítka jen za existující akcí. */
export default function CardFoot({ card, busy, onPanel, onRefresh, onAskHeart, onEnterCanvas, onWork }: Props) {
  const [asking, setAsking] = useState(false);
  const [working, setWorking] = useState(false);
  const [workError, setWorkError] = useState("");
  const submitWork = async (body: object) => {
    const error = await onWork(body);
    setWorkError(error);
    return !error;
  };
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const send = async () => {
    if (!onAskHeart || !card || !text.trim()) return;
    setSending(true);
    const ok = await onAskHeart(`Karta „${card.title}“ (${card.nodeId}): ${text.trim()}`);
    setSending(false);
    if (ok) { setText(""); setAsking(false); }
  };
  const preview = card?.output?.preview?.url;
  return <footer className="live-card__foot">
    <div className="live-card__foot-text">
      <b className="live-card__next">{card?.next ? `Další krok: ${card.next.text}` : "Další krok není určen"}</b>
      {card?.next?.why && <span className="live-card__why">{card.next.why}</span>}
      {card?.heart && <span className="live-card__why">Poslední zásah srdce {clock(card.heart.at)} {card.heart.severity ? ` (${card.heart.severity})` : ""}: {card.heart.text}</span>}
    </div>
    {asking && <form className="live-card__ask" onSubmit={event => { event.preventDefault(); void send(); }}>
      <input className="live-card__ask-input" value={text} onChange={event => setText(event.target.value)} placeholder="Na co se srdce zeptat…" aria-label="Otázka pro srdce" autoFocus />
      <button type="submit" className="live-card__button live-card__button--go" disabled={sending || !text.trim()}>{sending ? "Posílám…" : "Poslat"}</button>
    </form>}
    {working && card && <div className="live-card__work">
      <LinieWorkForm rows={[]} initial={workDraft(card)} onSubmit={submitWork} onClose={() => setWorking(false)} />
    </div>}
    {workError && <p className="live-card__alert" role="alert">{workError}</p>}
    <div className="live-card__acts">
      {card && !card.linie && !working && <button type="button" className="live-card__button" onClick={() => { setWorkError(""); setWorking(true); }}>Předat do Kanceláře</button>}
      {onAskHeart && card && !asking && <button type="button" className="live-card__button" onClick={() => setAsking(true)}>Zeptat se srdce</button>}
      {onEnterCanvas && <button type="button" className="live-card__button" onClick={onEnterCanvas}>Otevřít vnitřní plátno</button>}
      {preview && <a className="live-card__button" href={preview} target="_blank" rel="noreferrer">Otevřít náhled</a>}
      <button type="button" className="live-card__button" onClick={onRefresh} disabled={busy}>{busy ? "Načítám…" : "Obnovit"}</button>
      <button type="button" className="live-card__button live-card__button--go" onClick={onPanel}>Pracovní panel</button>
    </div>
  </footer>;
}
