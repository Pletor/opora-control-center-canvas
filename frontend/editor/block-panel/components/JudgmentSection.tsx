// „Potřebuje úsudek“: jen když smyčka nastavila příznak. Zlatý rámeček = otázka na člověka, červený =
// zaseklá kontrola (dvakrát červená). Panel jen čte: odpověď jde srdci, detail vede do Review nebo Běhu.
import { useState } from "react";
import type { CardTab } from "@/hub/oporahub-card-drawer/open";
import type { TrailJudgment } from "../logic/card-trail";
import type { JudgmentView } from "../logic/panel-work";
import SourceMark from "./SourceMark";

function Judgment({ item, view, onAnswer, onOpen }: {
  item: TrailJudgment; view: JudgmentView; onAnswer: (item: TrailJudgment, text: string) => Promise<boolean>; onOpen: (tab: CardTab) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  function send() {
    if (!draft.trim() || busy) return;
    setBusy(true);
    void onAnswer(item, draft).then((ok) => { setBusy(false); if (ok) { setDraft(""); setOpen(false); } });
  }
  return (
    <div className={"block-panel__judge block-panel__judge--" + view.tone} data-oh-judgment={item.code}>
      <div className="block-panel__judge-head">
        <span className="block-panel__judge-code">{view.label}</span>
        {view.where && <span>· {view.where}</span>}
        <span className="block-panel__grow" /><SourceMark source={item.source} />
      </div>
      {view.reason && <p className="block-panel__judge-text">{view.reason}</p>}
      {view.outside.length > 0 && <div className="block-panel__files">{view.outside.map((file) => <code key={file} className="block-panel__file">{file}</code>)}</div>}
      {view.heart && <div className="block-panel__judge-head block-panel__judge-head--heart"><SourceMark source="heart" /><span>{view.heart}</span></div>}
      {open && <textarea className="block-panel__reply" aria-label="Odpověď srdci" rows={3} value={draft} disabled={busy}
        placeholder="Co má srdce vědět nebo udělat" onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />}
      <div className="block-panel__judge-actions">
        {open
          ? <button type="button" className="block-panel__btn block-panel__btn--gold" disabled={busy || !draft.trim()} onClick={send}>Poslat srdci</button>
          : <button type="button" className="block-panel__btn block-panel__btn--gold" onClick={() => setOpen(true)}>Odpovědět srdci</button>}
        <button type="button" className="block-panel__link" onClick={() => onOpen(view.link.tab)}>{view.link.text}</button>
      </div>
    </div>
  );
}

export default function JudgmentSection({ items, views, onAnswer, onOpen }: {
  items: TrailJudgment[]; views: JudgmentView[]; onAnswer: (item: TrailJudgment, text: string) => Promise<boolean>; onOpen: (tab: CardTab) => void;
}) {
  if (!items.length) return null;
  return (
    <section className="block-panel__sec" aria-label="Potřebuje úsudek">
      <h3 className="block-panel__h">Potřebuje úsudek<span className="block-panel__count">{items.length}</span></h3>
      {items.map((item, index) => <Judgment key={views[index].key} item={item} view={views[index]} onAnswer={onAnswer} onOpen={onOpen} />)}
    </section>
  );
}
