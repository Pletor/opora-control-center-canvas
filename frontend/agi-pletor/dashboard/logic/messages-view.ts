import { list, rec, str } from "./view-common";

export type MessagesView = { messages: { role: string; at: string; text: string }[]; total: number };

/** Odpověď `GET /api/pletor/messages` → řádky se štítkem role (Člověk / Pletor); pořadí ze serveru, nejnovější poslední. */
export function messagesView(raw: unknown): MessagesView {
  const root = rec(raw);
  const messages = list(root.messages).map((item) => {
    const message = rec(item);
    return { role: message.role === "human" ? "Člověk" : "Pletor", at: str(message.at), text: str(message.text) };
  });
  return { messages, total: typeof root.total === "number" ? root.total : messages.length };
}

/** Adresa čtení rozhovoru; prázdné hledání se do adresy nedává. */
export const messagesUrl = (project: string, workspace: string, limit: number, q: string) =>
  `/api/pletor/messages?${new URLSearchParams({ project, workspace, limit: String(limit), ...(q.trim() ? { q: q.trim() } : {}) })}`;
