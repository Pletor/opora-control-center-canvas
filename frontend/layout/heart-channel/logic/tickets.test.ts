import { describe, expect, it } from "vitest";
import type { TicketFeedback, TicketStatus, WorkTicket } from "./heart-api";
import { groupTickets, holderLabel, lastFeedback, ticketTitle } from "./tickets";

const feedback = (seq: number, text: string, answeredAt: string | null = null): TicketFeedback =>
  ({ feedbackId: "f" + seq, seq, kind: "question", text, sessionId: "gs_abc", answer: null, answeredAt, createdAt: "2026-11-03T10:00:00Z" });

const ticket = (seq: number, status: TicketStatus, extra: Partial<WorkTicket> = {}): WorkTicket => ({
  ticketId: "t" + seq, seq, workspaceId: "w", status,
  body: { essence: "E", build: "Postav login\ndruhý řádek", openPaths: [], cautions: [], skills: [], doneCriteria: [] },
  machine: { cardId: null, executionId: null, cardVersion: null, successors: [], predecessors: [] }, sessionId: null, delivery: null, feedback: [],
  createdAt: "2026-11-03T10:00:00Z", updatedAt: "2026-11-03T10:00:00Z", ...extra,
});

describe("tickety srdce", () => {
  it("skupiny jdou v pořadí čtení, prázdné se vynechají a uvnitř podle seq", () => {
    const groups = groupTickets([ticket(3, "closed"), ticket(2, "issued"), ticket(1, "needs_answer"), ticket(4, "issued"), ticket(5, "draft")]);
    expect(groups.map((g) => [g.label, g.tickets.map((t) => t.seq)])).toEqual([
      ["Čeká na odpověď", [1]], ["Vydáno", [2, 4]], ["Uzavřeno", [3]],
    ]);
  });

  it("titulek je první neprázdný řádek build, jinak číslo", () => {
    expect(ticketTitle(ticket(1, "issued"))).toBe("Postav login");
    expect(ticketTitle(ticket(7, "issued", { body: { ...ticket(1, "issued").body, build: "\n  \n" } }))).toBe("Ticket 7");
  });

  it("držitel je zkrácená relace nebo pomlčka", () => {
    expect(holderLabel({ sessionId: "gs_abcdef123" })).toBe("relace abcdef");
    expect(holderLabel({ sessionId: null })).toBe("—");
  });

  it("poslední zpětná vazba a zda má odpověď", () => {
    expect(lastFeedback(ticket(1, "issued"))).toBeNull();
    const t = ticket(1, "needs_answer", { feedback: [feedback(2, "druhá"), feedback(1, "první", "2026-11-03T11:00:00Z")] });
    expect(lastFeedback(t)).toEqual({ text: "druhá", answered: false });
    expect(lastFeedback(ticket(1, "claimed", { feedback: [feedback(1, "ano", "2026-11-03T11:00:00Z")] }))).toEqual({ text: "ano", answered: true });
  });
});
