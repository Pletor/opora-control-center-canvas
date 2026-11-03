import type { TicketStatus, WorkTicket } from "./heart-api";

/** Skupiny ticketů v pořadí, jak je člověk čte: co čeká na něj, co čeká na dělníka, co se dělá, co je hotové a co ne. */
export const TICKET_ORDER: { status: TicketStatus; label: string }[] = [
  { status: "needs_answer", label: "Čeká na odpověď" },
  { status: "issued", label: "Vydáno" },
  { status: "claimed", label: "Vzato" },
  { status: "in_progress", label: "Rozpracováno" },
  { status: "delivered", label: "Odevzdáno" },
  { status: "verified", label: "Ověřeno" },
  { status: "failed", label: "Selhalo" },
  { status: "cancelled", label: "Zrušeno" },
  { status: "closed", label: "Uzavřeno" },
];

export type TicketGroup = { status: TicketStatus; label: string; tickets: WorkTicket[] };

/** Tickety → neprázdné skupiny v pořadí `TICKET_ORDER`; uvnitř skupiny podle `seq` (od nejstaršího). Koncepty se nezobrazují. */
export function groupTickets(tickets: WorkTicket[]): TicketGroup[] {
  return TICKET_ORDER.map(({ status, label }) => ({
    status,
    label,
    tickets: tickets.filter((ticket) => ticket.status === status).sort((a, b) => a.seq - b.seq),
  })).filter((group) => group.tickets.length > 0);
}

/** Titulek ticketu: první neprázdný řádek `body.build`, jinak číslo ticketu. */
export function ticketTitle(ticket: { seq?: number; body: { build: string } }): string {
  const first = ticket.body.build.split("\n").map((line) => line.trim()).find(Boolean);
  return first ?? (ticket.seq !== undefined ? `Ticket ${ticket.seq}` : "Ticket");
}

/** Kdo ticket drží: zkrácená relace dělníka, jinak pomlčka. */
export function holderLabel(ticket: { sessionId: string | null }): string {
  return ticket.sessionId ? `relace ${ticket.sessionId.replace(/^gs_/, "").slice(0, 6)}` : "—";
}

/** Poslední zpětná vazba dělníka: její text a zda už má odpověď; bez zpětné vazby `null`. */
export function lastFeedback(ticket: WorkTicket): { text: string; answered: boolean } | null {
  const last = [...ticket.feedback].sort((a, b) => a.seq - b.seq).at(-1);
  return last ? { text: last.text, answered: last.answeredAt !== null } : null;
}
