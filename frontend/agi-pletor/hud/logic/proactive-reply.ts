/**
 * Proaktivní zpráva Pletora (oznámení odpovědi nebo otázky srdce) přijde pollingem, ne jako odpověď na `send`,
 * takže ji efekt na `repliedAt` nikdy nepřečte. Tady se pozná: poslední zpráva je od Pletora a od jeho předchozí
 * zprávy nepsal člověk (řádky deníku `heart` se přeskočí; „člověk → heart → pletor“ je běžný tah člověka).
 * Nahlas mluví jen Pletor: zprávy člověka a deníku se nevrací nikdy.
 */
import type { PletorMessage } from "./pletor-client";

const keyOf = (message: PletorMessage | undefined) => (message ? `${message.at}\n${message.text}` : null);

/** `seen` = klíč poslední zprávy z minula; `undefined` = první načtení prostoru, historie se nečte, jen se zapamatuje. */
export function proactiveReply(messages: PletorMessage[], seen: string | null | undefined) {
  const last = messages.at(-1);
  const key = keyOf(last);
  if (seen === undefined || key === seen || last?.role !== "pletor") return { key, speak: null };
  const before = messages.slice(0, -1).reverse().find((message) => message.role !== "heart");
  return { key, speak: before?.role === "human" ? null : last };
}
