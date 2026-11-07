import type { Judgement, SummaryKey } from "./linie-summary";

/**
 * Glyf kuličky a legenda z jednoho klíče souhrnu (`summary.key`, docs/navrhy/2026-11-06-linie-rebrand.md §2a), ne ze
 * starého `state`; tvary podle prototypu Claude Design „Linie v3“. Jádro: `ghost` = ticket bez pokusu (šedé čárkované),
 * `open` = probíhá nebo odevzdáno bez prošlých kontrol (čárkované), `full` = kontroly prošly / začleněno (plné),
 * `plain` = obrys bez čárek, `parked` = odloženo (tečkované). Hal = čeká na člověka, žlutý prstenec = přijetí zastaralo,
 * červený střed = blok, `aim` = smí nést puntík cíle.
 */
export type Core = "ghost" | "open" | "full" | "plain" | "parked";
export type Glyph = { key: SummaryKey; core: Core; halo: boolean; staleRing: boolean; blocked: boolean; aim: boolean };

const CORE: Record<SummaryKey, Core> = {
  todo: "ghost", wip: "open", failed: "open", nocheck: "open", checking: "open",
  pending: "full", accepted: "full", stale: "full", merged: "full", blocked: "plain", parked: "parked", unknown: "plain",
};
const HALO: SummaryKey[] = ["pending", "accepted", "stale"];
const NO_AIM: SummaryKey[] = ["merged", "blocked", "todo"];

// OP-3C563E.1: tvar se bere jen ze souhrnu; „nocheck“ po starším přijetí nese stejný žlutý prstenec jako „stale“.
export function glyphOf(key: SummaryKey, judgement?: Pick<Judgement, "axes">): Glyph {
  const staleAccept = key === "nocheck" && judgement?.axes?.acceptance.state === "accepted";
  return { key, core: CORE[key], halo: HALO.includes(key), staleRing: key === "stale" || staleAccept, blocked: key === "blocked", aim: !NO_AIM.includes(key) };
}

/** Položky legendy jako v prototypu (+ odloženo a „nevím“, ať každý klíč někam patří); `keys` = co se počítá. */
export const LEGEND: { text: string; keys: SummaryKey[] }[] = [
  { text: "ticket bez pokusu", keys: ["todo"] },
  { text: "probíhá", keys: ["wip", "checking", "failed", "nocheck"] },
  { text: "odevzdáno, kontroly prošly", keys: ["pending", "accepted"] },
  { text: "přijetí zastaralo", keys: ["stale"] },
  { text: "začleněno (barva cíle)", keys: ["merged"] },
  { text: "blokováno", keys: ["blocked"] },
  { text: "odloženo", keys: ["parked"] },
  { text: "nevím", keys: ["unknown"] },
];

/** Legenda dole: glyf, text a počet kuliček podle `summary.key`; „nevím“ jen když taková kulička je. */
export function legend(balls: { judgement: Pick<Judgement, "summary"> }[]): { glyph: Glyph; text: string; count: number }[] {
  return LEGEND.map(({ text, keys }) => ({ glyph: glyphOf(keys[0]), text, count: balls.filter((b) => keys.includes(b.judgement.summary.key)).length }))
    .filter((item) => item.glyph.key !== "unknown" || item.count > 0);
}

/** Přípona popisku jako v prototypu: „ · 2 c“ živé commity, „ · 1 ✕“ opuštěné; nula se nepíše. */
export function commitTail(commits: { abandoned: boolean }[]): string {
  const dead = commits.filter((c) => c.abandoned).length, live = commits.length - dead;
  return `${live ? ` · ${live} c` : ""}${dead ? ` · ${dead} ✕` : ""}`;
}
