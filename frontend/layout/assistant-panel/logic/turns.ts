/**
 * Konverzace po tazích. Tah je zpráva uživatele a všechno, co po ní přišlo (kroky nástrojů, odpovědi
 * asistenta, chyby, konec tahu), až do další zprávy uživatele. Čisté funkce bez Reactu.
 *
 * Údaje hlavičky se berou jen z toho, co panel opravdu ví: čas odeslání zná jen u zprávy odeslané
 * z tohoto panelu, délku jen z `turn_end.durationMs` a kroky jen u živého tahu. Historie z přepisu
 * nemá ani čas, ani kroky, a tak je hlavička nevymýšlí.
 */
import type { ChatItem } from "./assistant-events";
import { groupEntries, stepsWord, type ConversationEntry } from "./tool-steps";

type Message = Extract<ChatItem, { kind: "message" }>;

export type Turn = {
  /** Pořadí od 1, „Tah N“. */
  index: number;
  /** Kotva v dokumentu pro osnovu (`id` prvku). */
  anchor: string;
  user: Message | null;
  entries: ConversationEntry[];
  /** Kdy uživatel zprávu odeslal (ms), jinak null. */
  startedAt: number | null;
  /** Součet `durationMs` z konců tahu, null když žádný konec délku neuvedl. */
  durationMs: number | null;
  /** Počet kroků nástrojů; null u tahu z historie, kde kroky neznáme. */
  steps: number | null;
  denied: number;
  /** Tah viděný naživo (události SSE nebo odeslaný odsud), ne jen přečtený z přepisu. */
  live: boolean;
  /** Konverzace tah uzavřela událostí `turn_end`. */
  ended: boolean;
};

export function turnAnchor(index: number): string {
  return `assistant-turn-${index}`;
}

/** Kotva karty otázky: id zprávy a číslo otázky, jen znaky povolené v `id`. */
export function decisionAnchor(messageId: string, questionId: string): string {
  return `assistant-q-${messageId}-${questionId}`.replace(/[^A-Za-z0-9_-]/g, "_");
}

export function buildTurns(items: ChatItem[]): Turn[] {
  const groups: { user: Message | null; rest: ChatItem[] }[] = [];
  for (const item of items) {
    if (item.kind === "message" && item.role === "user") groups.push({ user: item, rest: [] });
    else if (groups.length) groups[groups.length - 1].rest.push(item);
    else groups.push({ user: null, rest: [item] });
  }
  return groups.map(({ user, rest }, i) => {
    const all = user ? [user, ...rest] : rest;
    const ends = rest.filter((it): it is Extract<ChatItem, { kind: "turn_end" }> => it.kind === "turn_end");
    const tools = rest.filter((it) => it.kind === "tool").length;
    const live = all.some((it) => it.kind !== "message" || it.origin !== "history");
    const durations = ends.map((e) => e.durationMs).filter((d): d is number => typeof d === "number");
    return {
      index: i + 1,
      anchor: turnAnchor(i + 1),
      user,
      entries: groupEntries(rest),
      startedAt: user && typeof user.at === "number" ? user.at : null,
      durationMs: durations.length ? durations.reduce((a, b) => a + b, 0) : null,
      steps: live ? tools : null,
      denied: ends.reduce((sum, e) => sum + e.denied, 0),
      live,
      ended: ends.length > 0,
    };
  });
}

/** „38 s“, „2 min 5 s“, „1 h 4 min“. */
export function formatDuration(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  if (total < 60) return `${total} s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return total % 60 ? `${minutes} min ${total % 60} s` : `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return minutes % 60 ? `${hours} h ${minutes % 60} min` : `${hours} h`;
}

/** Čas odeslání v místním čase „14:02“. */
export function clockTime(at: number): string {
  const date = new Date(at);
  return `${date.getHours()}:${String(date.getMinutes()).padStart(2, "0")}`;
}

/** Údaje hlavičky tahu za „Tah N“: jen to, co je známé. */
export function turnMeta(turn: Turn): string[] {
  const parts: string[] = [];
  if (turn.startedAt !== null) parts.push(clockTime(turn.startedAt));
  if (turn.durationMs !== null) parts.push(formatDuration(turn.durationMs));
  if (turn.steps !== null && turn.steps > 0) parts.push(`${turn.steps} ${stepsWord(turn.steps)}`);
  return parts;
}

/** První slova zprávy uživatele pro osnovu; tah bez zprávy je „Začátek“. */
export function turnLabel(turn: Turn, max = 48): string {
  const text = (turn.user?.text ?? "").replace(/\s+/g, " ").trim();
  if (!text) return "Začátek";
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const space = cut.lastIndexOf(" ");
  return (space > max / 2 ? cut.slice(0, space) : cut).replace(/[\s,.;:–-]+$/, "") + "…";
}

/** Poslední odpověď asistenta v konverzaci (zdroj otázek k rozhodnutí v osnově). */
export function lastAnswer(items: ChatItem[]): Message | null {
  for (let i = items.length - 1; i >= 0; i--) {
    const item = items[i];
    if (item.kind === "message" && item.role === "assistant" && item.text.trim()) return item;
  }
  return null;
}

/** Souhrn kroků celé konverzace; null, když konverzace žádné živé údaje nemá (jen historie). */
export function stepsSummary(turns: Turn[]): { steps: number; denied: number } | null {
  const live = turns.filter((t) => t.live);
  if (!live.length) return null;
  return { steps: live.reduce((sum, t) => sum + (t.steps ?? 0), 0), denied: live.reduce((sum, t) => sum + t.denied, 0) };
}
