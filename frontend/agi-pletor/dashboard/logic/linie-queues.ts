import type { BoardBall, BoardQueues } from "./linie-board";

/**
 * Fronty odpovědnosti nad lištou (docs/navrhy/2026-11-06-linie-rebrand.md §6): kdo má míč. Počty dává board
 * (`queues`, L7d) a otevřené žádosti (`GET /api/pletor/requests?open=1`); kuličky ve frontě říká `ball.queues`, kulička
 * smí být ve více frontách. Zdroj, který board nenese (`null`), počet nevymýšlí a hlásí „— (nedostupné)“.
 */
export type QueueId = "clovek" | "pletor" | "srdce" | "tickety" | "kancelar" | "git";
export type Queue = { id: QueueId; label: string; count: string; hint: string; ids: string[]; source: boolean };
export type QueueBall = Pick<BoardBall, "ticketId" | "queues">;

/** Česky: 1 úkol, 2–4 úkoly, 0 a 5+ úkolů. */
export const plural = (n: number, one: string, few: string, many: string) => `${n} ${n === 1 ? one : n >= 2 && n <= 4 ? few : many}`;

const NAME: Record<Exclude<QueueId, "pletor" | "srdce">, keyof Omit<BoardQueues, "plansWaiting">> = { clovek: "humanDecisions", tickety: "ticketsTodo", kancelar: "officeTasks", git: "gitQueue" };
export const NO_SOURCE = "— (nedostupné)";

/** Výrok Pletora bez výběru: jen počty front, které mají zdroj, a co člověk může udělat dál. */
export function queueLines(list: Queue[], balls: number): string[] {
  return [
    `Na plátně ${plural(balls, "kulička", "kuličky", "kuliček")}.`,
    ...list.filter((q) => q.source).map((q) => `${q.label}: ${q.count}.`),
    "Klikni na kuličku nebo frontu; řeknu, co o ní vím, odkud a co je další krok.",
  ];
}

/** `counts` z boardu (null = board bez front), `openRequests` z /api/pletor/requests (null = nenačteno). */
export function queues(balls: QueueBall[], counts: BoardQueues | null, openRequests: number | null): Queue[] {
  const ids = (id: keyof typeof NAME) => balls.filter((b) => b.queues.includes(NAME[id])).map((b) => b.ticketId);
  const of = (id: keyof typeof NAME, one: string, few: string, many: string) => {
    const n = counts?.[NAME[id]] ?? null;
    return { ids: ids(id), count: n === null ? NO_SOURCE : plural(n, one, few, many), source: n !== null };
  };
  const plans = counts?.plansWaiting ?? null;
  return [
    { id: "clovek", label: "Člověk", hint: "přijetí, zastaralé přijetí, odblokování", ...of("clovek", "rozhodnutí", "rozhodnutí", "rozhodnutí") },
    { id: "pletor", label: "Pletor", hint: "žádosti srdci bez potvrzeného commitu", ids: [], count: openRequests === null ? NO_SOURCE : plural(openRequests, "otevřená žádost", "otevřené žádosti", "otevřených žádostí"), source: openRequests !== null },
    { id: "srdce", label: "Srdce", hint: "karty plánu (plátno 3) bez vydaného ticketu", ids: [], count: plans === null ? NO_SOURCE : plural(plans, "plán", "plány", "plánů"), source: plans !== null },
    { id: "tickety", label: "Tickety", hint: "čekají na pokus · značka OP-", ...of("tickety", "ticket", "tickety", "ticketů") },
    { id: "kancelar", label: "Kancelář", hint: "probíhá, selhalo, bez kontrol", ...of("kancelar", "úkol", "úkoly", "úkolů") },
    { id: "git", label: "Git", hint: "kontroly běží, přijato k začlenění, otevřený PR", ...of("git", "PR", "PR", "PR") },
  ];
}
