import { list, rec, str } from "./view-common";

/**
 * Žádosti srdci z `GET /api/pletor/requests?open=1` (docs/navrhy/2026-11-06-linie-rebrand.md §4a, §6): řetězec kroků
 * přijato · plán · ticket · relace · commit. Krok se ukáže jako hotový až s potvrzeným důkazem, selhání zůstává červeně
 * viditelné (žádost se opakuje stejným klíčem). Čistá logika bez Reactu.
 */
export type StepState = "ok" | "fail" | "wait";
export type RequestStep = { k: string; text: string; state: StepState; why: string };
export type HeartRequest = { id: string; text: string; at: string; steps: RequestStep[]; open: boolean };

const CHAIN: [string, string][] = [["accepted", "žádost přijata"], ["plan", "plán (srdce)"], ["ticket", "ticket"], ["attempt", "relace kanceláře"], ["commit", "commit"]];

export function requestsView(raw: unknown): HeartRequest[] {
  return list(rec(raw).requests).map((item) => {
    const r = rec(item);
    const steps = list(r.steps).map(rec);
    const chain = CHAIN.map(([k, text]) => {
      const mine = steps.filter((s) => str(s.k) === k);
      const done = mine.find((s) => s.failed !== true), failed = mine.filter((s) => s.failed === true).at(-1);
      // Hotový krok vítězí nad dřívějším selháním (opakování stejným klíčem); jinak zůstává selhání vidět.
      const state: StepState = done ? "ok" : failed ? "fail" : "wait";
      return { k, text, state, why: !done && failed ? str(failed.why) : "" };
    });
    return { id: str(r.id), text: str(r.text), at: str(r.at), steps: chain, open: !chain.find((s) => s.k === "commit" && s.state === "ok") };
  }).filter((r) => r.id);
}

/** Klíč idempotence pro jednu žádost z textu: opakované odeslání téhož textu nevyrobí druhou žádost. */
export const requestKey = (text: string, nonce: string) => `ui-${nonce}-${text.trim().length}`;
