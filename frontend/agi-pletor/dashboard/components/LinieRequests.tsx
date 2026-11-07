import { useState, type KeyboardEvent } from "react";
import type { HeartRequest } from "../logic/linie-requests";

type Props = { requests: HeartRequest[] | null; onAsk: (text: string) => Promise<string> };

/**
 * „Zadat srdci“ a řetězce žádostí pod ním (§4a): po odeslání vznikne hned jen „žádost přijata“; plán, ticket, relace
 * a commit se rozsvítí až s potvrzením každého kroku ze služby. Selhání zůstává červeně, opakování nese stejný klíč.
 */
export default function LinieRequests({ requests, onAsk }: Props) {
  const [text, setText] = useState("");
  const [said, setSaid] = useState("");
  const send = () => {
    if (!text.trim()) { setSaid("Napiš zadání."); return; }
    const asked = text;
    setText("");
    void onAsk(asked).then(setSaid);
  };
  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); send(); } };
  return (
    <>
      <textarea className="pletor-dashboard__input pletor-dashboard__linie-pletor-ask" aria-label="Zadat srdci" value={text} onChange={(event) => setText(event.target.value)} onKeyDown={onKey}
        placeholder="Změna plánu nebo zadání… Pletor zapíše „žádost přijata“; plán, ticket, relace a commit se objeví až po potvrzení každého kroku." />
      <span className="pletor-dashboard__tools">
        <button type="button" className="pletor-dashboard__button" onClick={send}>Zadat srdci (Ctrl+Enter)</button>
        {said && <span className="pletor-dashboard__note" role="status">{said}</span>}
      </span>
      {requests === null && <p className="pletor-dashboard__note">Žádosti srdci: zdroj nedostupný.</p>}
      {requests?.map((request) => (
        <div key={request.id} className="pletor-dashboard__linie-request">
          <div className="pletor-dashboard__linie-request-head"><span className="pletor-dashboard__linie-request-text" title={request.text}>{request.text}</span><span className="pletor-dashboard__mono">{request.id}</span></div>
          <div className="pletor-dashboard__linie-chain">
            {request.steps.map((step) => <span key={step.k} className={`pletor-dashboard__linie-step pletor-dashboard__linie-step--${step.state}`} title={step.why || undefined}>{step.text}</span>)}
          </div>
        </div>
      ))}
    </>
  );
}
