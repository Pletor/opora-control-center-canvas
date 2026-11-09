import { useState } from "react";
import type { useSessionView } from "../logic/use-session-view";
import "../styles/session-view.css";

export default function SessionViewControl({ view }: { view: ReturnType<typeof useSessionView> }) {
  const [selected, setSelected] = useState("");
  return <details className="session-view"><summary>Pohled srdce{view.attached ? (view.applied ? " · zobrazen" : " · připojen") : ""}</summary>
    <p>Připojení ovládá pouze výběr, kameru, filtr a sbalení skupin Struktury této karty prohlížeče.</p>
    {view.attached ? <><p>Relace <code>{view.sessionId}</code></p><button onClick={view.retry}>Použít znovu</button> <button onClick={() => void view.detach()}>Odpojit pohled</button></> : <>
      <label>Relace srdce <select aria-label="Relace srdce pro pohled" value={selected} onChange={event => setSelected(event.target.value)}>
        <option value="">Vyberte relaci</option>{view.sessions.map(session => <option key={session.sessionId} value={session.sessionId}>{session.createdAt} · {session.sessionId}</option>)}
      </select></label> <button onClick={() => void view.refresh()}>Obnovit relace</button> <button disabled={!selected} onClick={() => void view.attach(selected)}>Připojit tuto kartu</button>
    </>}
    <p role="status">{view.message}</p>
  </details>;
}
