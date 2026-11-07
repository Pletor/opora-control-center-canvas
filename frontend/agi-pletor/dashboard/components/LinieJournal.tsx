import { useState } from "react";
import { unseenCount, type Journal } from "../logic/linie-journal";
import { hhmm } from "../logic/linie-summary";

type Props = { journal: Journal; marks: Record<string, string>; onPick: (ticketId: string) => void };

/**
 * Deník dole, výchozí sbalený s počtem nových událostí od posledního rozbalení. Řádek = čas · druh · kdo · značka a
 * věta; klik označí kuličku, které událost patří. Zdroj je evidence backendu (`/journal`), ne prohlížeč.
 */
export default function LinieJournal({ journal, marks, onPick }: Props) {
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState(0);
  const fresh = unseenCount(journal, seen);
  const toggle = () => { setOpen(!open); setSeen(journal.lastId); };
  return (
    <section className={`pletor-dashboard__linie-journal${open ? " pletor-dashboard__linie-journal--open" : ""}`} aria-label="Deník procesu">
      <button type="button" className="pletor-dashboard__linie-journal-head" aria-expanded={open} onClick={toggle}>
        <span>Deník · {journal.events.length} záznamů</span>
        {fresh > 0 && <span className="pletor-dashboard__linie-journal-badge">{fresh} nových</span>}
        <span>kdo · co · kdy · klik = označí kuličku</span>
        <span className="pletor-dashboard__linie-journal-toggle">{open ? "sbalit ▾" : "rozbalit ▸"}</span>
      </button>
      {open && (
        <div className="pletor-dashboard__linie-journal-body">
          {[...journal.events].reverse().map((event) => (
            <div key={event.id} className={`pletor-dashboard__linie-journal-row${event.id > seen ? " pletor-dashboard__linie-journal-row--new" : ""}`} role={event.ticketId ? "button" : undefined} tabIndex={event.ticketId ? 0 : undefined}
              onClick={() => event.ticketId && onPick(event.ticketId)} onKeyDown={(e) => { if (event.ticketId && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onPick(event.ticketId); } }}>
              <span className="pletor-dashboard__linie-journal-time">{hhmm(event.at)}</span>
              <span className={`pletor-dashboard__linie-journal-kind${event.failed ? " pletor-dashboard__linie-journal-kind--failed" : ""}`}>{event.kindText}</span>
              <span className="pletor-dashboard__linie-journal-who">{event.who}</span>
              <span className="pletor-dashboard__linie-journal-text"><span className="pletor-dashboard__mono">{marks[event.ticketId] ?? ""}</span> {event.text}</span>
            </div>
          ))}
          {!journal.events.length && <p className="pletor-dashboard__note">Deník je prázdný.</p>}
        </div>
      )}
    </section>
  );
}
