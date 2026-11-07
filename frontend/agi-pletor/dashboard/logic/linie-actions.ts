import type { Judgement } from "./linie-summary";
import type { WorkDetail } from "./linie-work";

/**
 * Jediná cesta pro akce kuličky (docs/navrhy/2026-11-06-linie-rebrand.md §2a): co jde stisknout, říká jen `allowed`,
 * proč ne, jen `blocked`. Panel Pletora i záložka Git kreslí tentýž seznam. Dokud detail nenese tutéž revizi jako board,
 * je všechno zablokované, aby se nepřijalo staré `headSha` s novým `allowed`.
 */
export type PletorAction = { id: string; label: string; enabled: boolean; why: string };
export type ActionRequest = { path: string; body: object; method: "POST" | "DELETE"; done: string };

const LABEL: Record<string, string> = {
  accept: "Přijmout", allow_merge: "Povolit začlenění", merge: "Začlenit", block: "Blokovat", unblock: "Odblokovat",
  defer: "Odložit", park: "Odložit", resume: "Obnovit", preview: "Spustit náhled", revoke_accept: "Zrušit přijetí", attempt: "Založit pokus",
};
const ROUTED = new Set(["accept", "allow_merge", "merge", "block", "defer", "park", "resume", "preview", "revoke_accept"]); // = case v actionRequest
const short = (sha: string) => sha.slice(0, 7);

/** Board (sha7) a otevřený detail (plná hlava) mluví o téže revizi; kulička bez commitu revizi nemá. */
export const sameRevision = (boardSha7: string, detailSha: string) => !boardSha7 || (!!detailSha && detailSha.startsWith(boardSha7));

/** Trasa a tělo akce; `null` = backend pro ni trasu nemá (unblock, attempt). `note` = poznámka člověka k přijetí (smí být prázdná). */
export function actionRequest(id: string, ticketId: string, d: WorkDetail, note = ""): ActionRequest | null {
  const path = `/work/${encodeURIComponent(ticketId)}`;
  switch (id) {
    case "accept": return { path: `${path}/accept`, body: { sha: d.headSha, note }, method: "POST", done: `Přijato ${short(d.headSha)}.` };
    case "allow_merge": return { path: `${path}/allow-merge`, body: { target: d.target }, method: "POST", done: `Začlenění do ${d.target} povoleno.` };
    case "merge": return { path: `${path}/merge`, body: {}, method: "POST", done: "Začleněno službou." };
    case "block": return { path: `${path}/block`, body: { reason: "blokováno člověkem z Linie" }, method: "POST", done: "Zablokováno." };
    case "defer": case "park": return { path: `${path}/defer`, body: {}, method: "POST", done: "Odloženo." };
    case "resume": return { path: `${path}/resume`, body: {}, method: "POST", done: "Obnoveno." };
    case "preview": return { path: `${path}/preview`, body: {}, method: "POST", done: "Náhled se spouští." };
    case "revoke_accept": return { path: `${path}/accept`, body: {}, method: "DELETE", done: "Přijetí zrušeno." };
    default: return null;
  }
}

// OP-159D4C.3: akce jen z allowed/blocked a jen nad shodnou revizí boardu a detailu.
export function actionsOf(j: Judgement, ticketId: string, boardSha7: string, detail: WorkDetail | null): PletorAction[] {
  const synced = !!detail && detail.ticketId === ticketId && sameRevision(boardSha7, detail.headSha);
  return [...new Set([...j.allowed, ...Object.keys(j.blocked)])].map((id) => {
    const label = id === "accept" && synced && detail!.headSha ? `Přijmout ${short(detail!.headSha)}` : LABEL[id] ?? id;
    if (!j.allowed.includes(id)) return { id, label, enabled: false, why: j.blocked[id] || "pravidlo akci nepovoluje" };
    if (!ROUTED.has(id)) return { id, label, enabled: false, why: "operace zatím bez API (L7 PR 5)" };
    if (!synced) return { id, label, enabled: false, why: "načítám aktuální revizi" };
    return { id, label, enabled: true, why: "" };
  });
}
