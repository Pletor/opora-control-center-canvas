// Affiliate webu `settings.affiliate` (backend `backend/project/site_admin/site_settings.py`): parametr odkazu
// partnera, doba cookie, atribuce a provizní programy. Cookie s kódem partnera je marketingová, proto ji web smí
// uložit až po souhlasu v cookie liště (kategorie marketing).
import { HTTPS, readPart } from "@/project/site-admin/site-fields/logic/settings-part";

export type Program = { name: string; url: string; commission: string; code: string };
export type Affiliate = { enabled: boolean; param: string; cookieDays: number; attribution: string; disclosure: string; programs: Program[] };

export const EMPTY_AFFILIATE: Affiliate = { enabled: false, param: "ref", cookieDays: 30, attribution: "last", disclosure: "", programs: [] };
export const EMPTY_PROGRAM: Program = { name: "", url: "", commission: "", code: "" };
export const MAX_PROGRAMS = 50;

export const readAffiliate = (settings: Record<string, unknown>): Affiliate => readPart(settings, "affiliate", EMPTY_AFFILIATE);

const PARAM = /^[a-z][a-z0-9_-]{0,31}$/;
export const paramProblem = (param: string): string => PARAM.test(param) ? "" : "Parametr je malými písmeny a-z, 0-9, _ a - (ref, partner).";

/** Co programu chybí, aby ho server přijal. */
export function programProblem(program: Program): string {
  if (!program.name.trim()) return "Program potřebuje jméno.";
  return !program.url.trim() || HTTPS.test(program.url.trim()) ? "" : "Adresa programu je https://…";
}

/** Ukázkový odkaz partnera: `https://host/?ref=KOD`. */
export function partnerLink(host: string, param: string, code: string): string {
  let url: URL;
  try { url = new URL("https://" + (host || "www.example.cz") + "/"); } catch { url = new URL("https://www.example.cz/"); }
  url.searchParams.set(param || "ref", code || "PARTNER");
  return url.toString();
}

/** Věta, jak se provize přičte: první nebo poslední partner v době platnosti cookie. */
export const attributionText = (affiliate: Affiliate): string => affiliate.attribution === "first"
  ? `Provizi dostane první partner, přes kterého návštěvník přišel, pokud nakoupí do ${affiliate.cookieDays} dní.`
  : `Provizi dostane poslední partner před nákupem; cookie platí ${affiliate.cookieDays} dní od posledního kliknutí.`;
