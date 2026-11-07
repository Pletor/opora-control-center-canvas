import type { SummaryKey } from "./linie-summary";

/**
 * Fronty odpovědnosti nad lištou (docs/navrhy/2026-11-06-linie-rebrand.md §6): kdo má míč. Kulička se řadí podle
 * `summary.key` a smí být ve více frontách. Fronty, pro které zatím není zdroj (žádosti Pletora, plány srdce), počet
 * nevymýšlejí a hlásí „— (zatím bez zdroje)“.
 */
export type QueueId = "clovek" | "pletor" | "srdce" | "tickety" | "kancelar" | "git";
export type Queue = { id: QueueId; label: string; count: string; hint: string; ids: string[]; source: boolean };
export type QueueBall = { ticketId: string; key: SummaryKey; openPr: boolean };

/** Česky: 1 úkol, 2–4 úkoly, 0 a 5+ úkolů. */
export const plural = (n: number, one: string, few: string, many: string) => `${n} ${n === 1 ? one : n >= 2 && n <= 4 ? few : many}`;

const BY_KEY: Record<"clovek" | "tickety" | "kancelar" | "git", SummaryKey[]> = {
  clovek: ["pending", "stale", "blocked"],
  tickety: ["todo"],
  kancelar: ["wip", "failed", "nocheck"],
  git: ["checking", "accepted"],
};
const NO_SOURCE = "— (zatím bez zdroje)";

/** Výrok Pletora bez výběru: jen počty front, které mají zdroj, a co člověk může udělat dál. */
export function queueLines(list: Queue[], balls: number): string[] {
  return [
    `Na plátně ${plural(balls, "kulička", "kuličky", "kuliček")}.`,
    ...list.filter((q) => q.source).map((q) => `${q.label}: ${q.count}.`),
    "Klikni na kuličku nebo frontu; řeknu, co o ní vím, odkud a co je další krok.",
  ];
}

export function queues(balls: QueueBall[]): Queue[] {
  const of = (id: keyof typeof BY_KEY) => balls.filter((b) => BY_KEY[id].includes(b.key) || (id === "git" && b.openPr)).map((b) => b.ticketId);
  const clovek = of("clovek"), tickety = of("tickety"), kancelar = of("kancelar"), git = of("git");
  return [
    { id: "clovek", label: "Člověk", count: `${clovek.length} rozhodnutí`, hint: "přijetí, zastaralé přijetí, blokováno", ids: clovek, source: true },
    { id: "pletor", label: "Pletor", count: NO_SOURCE, hint: "žádosti čekají na /api/pletor/requests", ids: [], source: false },
    { id: "srdce", label: "Srdce", count: NO_SOURCE, hint: "plány plátna 3 board zatím nenese", ids: [], source: false },
    { id: "tickety", label: "Tickety", count: plural(tickety.length, "ticket", "tickety", "ticketů"), hint: "čekají na pokus", ids: tickety, source: true },
    { id: "kancelar", label: "Kancelář", count: plural(kancelar.length, "úkol", "úkoly", "úkolů"), hint: "probíhá, selhalo, bez kontrol", ids: kancelar, source: true },
    { id: "git", label: "Git", count: `${git.length} PR`, hint: "kontroly běží, přijato k začlenění, otevřený PR", ids: git, source: true },
  ];
}
