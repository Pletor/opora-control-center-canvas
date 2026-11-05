import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { messagesUrl, messagesView } from "../logic/messages-view";

/** Rozhovor: hledání v textu (debounce 300 ms), limit 50 / 200 a zprávy z `GET /api/pletor/messages`, nejnovější dole. */
export default function DashboardMessages({ project, workspace }: { project: string; workspace: string }) {
  const [input, setInput] = useState("");
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(50);
  const [raw, setRaw] = useState<unknown>(null);
  const [error, setError] = useState("");
  useEffect(() => { const timer = setTimeout(() => setQ(input), 300); return () => clearTimeout(timer); }, [input]);
  useEffect(() => {
    let live = true;
    api<unknown>(messagesUrl(project, workspace, limit, q)).then(
      (next) => { if (live) { setRaw(next); setError(""); } },
      (failure: unknown) => { if (live) setError(failure instanceof Error ? failure.message : "Načtení selhalo."); },
    );
    return () => { live = false; };
  }, [project, workspace, limit, q]);
  const view = messagesView(raw);
  return (
    <>
      <div className="pletor-dashboard__tools">
        <input type="search" className="pletor-dashboard__input" placeholder="Hledat v rozhovoru" aria-label="Hledat v rozhovoru" value={input} onChange={(event) => setInput(event.target.value)} />
        <select className="pletor-dashboard__input" aria-label="Počet zpráv" value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
          <option value={50}>50 zpráv</option>
          <option value={200}>200 zpráv</option>
        </select>
        <span className="pletor-dashboard__card-note">celkem {view.total}</span>
      </div>
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      <ul className="pletor-dashboard__messages">
        {view.messages.map((message, index) => (
          <li key={index} className="pletor-dashboard__message">
            <span className="pletor-dashboard__tag">{message.role}</span> <span className="pletor-dashboard__card-note">{message.at}</span>
            <p className="pletor-dashboard__message-text">{message.text}</p>
          </li>
        ))}
        {view.messages.length === 0 && <li className="pletor-dashboard__empty">Žádné zprávy.</li>}
      </ul>
    </>
  );
}
