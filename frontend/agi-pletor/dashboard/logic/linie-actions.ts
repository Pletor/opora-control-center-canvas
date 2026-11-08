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
  defer: "Odložit", park: "Odložit", resume: "Obnovit", preview: "Vyzkoušet", revoke_accept: "Zrušit přijetí", attempt: "Založit pokus",
  accept_untested: "přijmout bez zkoušky",
};
const ROUTED = new Set(["accept", "allow_merge", "merge", "block", "unblock", "defer", "park", "resume", "preview", "revoke_accept"]); // = case v actionRequest
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
    case "unblock": return { path: `${path}/unblock`, body: {}, method: "POST", done: "Odblokováno." };
    case "defer": case "park": return { path: `${path}/defer`, body: {}, method: "POST", done: "Odloženo." };
    case "resume": return { path: `${path}/resume`, body: {}, method: "POST", done: "Obnoveno." };
    case "accept_untested": return { path: `${path}/accept`, body: { sha: d.headSha, note, untested: true }, method: "POST", done: `Přijato ${short(d.headSha)} bez zkoušky.` };
    case "preview": return { path: `${path}/preview`, body: {}, method: "POST", done: "Náhled se spouští." };
    // Zkouška a obnova dat nejsou v `allowed`: týkají se jen běžícího náhledu (docs/navrhy/2026-11-08-linie-zkouska.md §5, §6).
    case "tried": return { path: `${path}/tried`, body: {}, method: "POST", done: `Zkouška zapsána na ${short(d.trial.sha)}.` };
    case "fresh": return { path: `${path}/preview`, body: { fresh: true }, method: "POST", done: "Náhled se přestaví s čerstvými daty z ostrých." };
    case "revoke_accept": return { path: `${path}/accept`, body: {}, method: "DELETE", done: "Přijetí zrušeno." };
    default: return null;
  }
}

/** Panel Pletora nese jen hlavní krok (nejvýš tři): blokovanou kuličku odblokovat, jinou přijmout → povolit → začlenit. Zbytek patří záložce Git. */
export function splitActions(actions: PletorAction[], key: string): { main: PletorAction[]; rest: PletorAction[] } {
  const wanted = key === "blocked" ? ["unblock"] : ["accept", "allow_merge", "merge"];
  const main = wanted.flatMap((id) => actions.filter((a) => a.id === id));
  return { main, rest: actions.filter((a) => !main.includes(a)) };
}

// OP-159D4C.3: akce jen z allowed/blocked a jen nad shodnou revizí boardu a detailu.
// Přijímá se vyzkoušená hlava (zkouška §7): bez platné zkoušky je Přijmout zamčené a vedle stojí „přijmout bez zkoušky“.
export function actionsOf(j: Judgement, ticketId: string, boardSha7: string, detail: WorkDetail | null): PletorAction[] {
  return ruleActions(j, ticketId, boardSha7, detail).flatMap((a) => (a.id === "accept" && a.enabled && !detail!.trial.triedCurrent
    ? [{ ...a, enabled: false, why: "nejdřív Vyzkoušet: přijímá se hlava, kterou jsi zkoušel" }, { id: "accept_untested", label: LABEL.accept_untested, enabled: true, why: "" }]
    : [a]));
}

function ruleActions(j: Judgement, ticketId: string, boardSha7: string, detail: WorkDetail | null): PletorAction[] {
  const synced = !!detail && detail.ticketId === ticketId && sameRevision(boardSha7, detail.headSha);
  return [...new Set([...j.allowed, ...Object.keys(j.blocked)])].map((id) => {
    const label = id === "accept" && synced && detail!.headSha ? `Přijmout ${short(detail!.headSha)}` : LABEL[id] ?? id;
    if (!j.allowed.includes(id)) return { id, label, enabled: false, why: j.blocked[id] || "pravidlo akci nepovoluje" };
    if (!ROUTED.has(id)) return { id, label, enabled: false, why: "pokus zakládá kancelář (větev z rodiče podle jména), ne tlačítko" };
    if (!synced) return { id, label, enabled: false, why: "načítám aktuální revizi" };
    return { id, label, enabled: true, why: "" };
  });
}
