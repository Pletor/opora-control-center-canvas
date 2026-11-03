import type { WorkTicket } from "../logic/heart-api";
import { groupTickets, holderLabel, lastFeedback, ticketTitle } from "../logic/tickets";

/** Řádek ticketu: titulek, stav, karta a poslední zpětná vazba; rozbalí se na essence a doneCriteria. Jen ke čtení. */
function TicketRow({ ticket, label }: { ticket: WorkTicket; label: string }) {
  const feedback = lastFeedback(ticket);
  const criteria = ticket.body.doneCriteria;
  return (
    <li className="heart-channel__ticket">
      <details className="heart-channel__ticket-details">
        <summary className="heart-channel__ticket-summary">
          <span className="heart-channel__ticket-title">{ticketTitle(ticket)}</span>
          <span className={`heart-channel__ticket-status heart-channel__ticket-status--${ticket.status}`}>{label}</span>
          {ticket.machine.cardId && <span className="heart-channel__ticket-card">{ticket.machine.cardId}</span>}
          <span className="heart-channel__ticket-holder">{holderLabel(ticket)}</span>
        </summary>
        {feedback && (
          <p className={`heart-channel__ticket-feedback${feedback.answered ? "" : " heart-channel__ticket-feedback--open"}`}>
            {feedback.text}{feedback.answered ? " (zodpovězeno)" : " (čeká na odpověď)"}
          </p>
        )}
        <p className="heart-channel__ticket-essence">{ticket.body.essence}</p>
        {criteria.length > 0 && (
          <ul className="heart-channel__ticket-criteria" aria-label="Hotovo, když">
            {criteria.map((item, index) => <li key={index}>{item}</li>)}
          </ul>
        )}
      </details>
    </li>
  );
}

/** Tickety pracovního prostoru po skupinách podle stavu (pořadí čtení v `TICKET_ORDER`). */
export default function Tickets({ tickets, loaded }: { tickets: WorkTicket[]; loaded: boolean }) {
  const groups = groupTickets(tickets);
  return (
    <section className="heart-channel__section" aria-label="Tickety">
      <h3 className="heart-channel__heading">Tickety</h3>
      {groups.length === 0 && <p className="heart-channel__empty">{loaded ? "Žádné tickety." : "Načítám tickety…"}</p>}
      {groups.map((group) => (
        <div key={group.status} className="heart-channel__group">
          <h4 className="heart-channel__group-label">
            {group.label} <span className="heart-channel__count">{group.tickets.length}</span>
          </h4>
          <ul className="heart-channel__tickets">
            {group.tickets.map((ticket) => <TicketRow key={ticket.ticketId} ticket={ticket} label={group.label} />)}
          </ul>
        </div>
      ))}
    </section>
  );
}
