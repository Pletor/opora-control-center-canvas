// Odznak ověření cesty zákazníka (docs/brana-cesty.md §4–§5): co ukázat u cesty
// Editoru stránky. Čistá logika bez Reactu, sdílená oběma místy; data jsou `lastRun` z `GET .../journeys`.
// Pořadí důvodů je stejné jako v bráně uzavření karty: chybí → zastaralé → neprošlo.
import type { DerivedJourney } from "./derived-journeys";

/** `ok` = karta na cestě se smí uzavřít; ostatní stavy uzavření brání. */
export type VerificationTone = "ok" | "stale" | "failed" | "none";
export type VerificationBadge = { tone: VerificationTone; text: string; at: string | null; command: string | null };

/** Odznak cesty, nebo `null`, když odvození cesty chybí (backend neodpověděl) nebo je cesta rozbitá (plán nemá). */
export function verificationBadge(derived: DerivedJourney | undefined): VerificationBadge | null {
  if (!derived || derived.broken) return null;
  const run = derived.lastRun;
  if (!run) return { tone: "none", text: "Neověřeno", at: null, command: null };
  const meta = { at: run.at, command: run.command || null };
  if (run.stale) return { tone: "stale", text: "Ověření zastaralé", ...meta };
  if (run.passed) return { tone: "ok", text: "Ověřeno", ...meta };
  const first = run.firstFailure;
  const text = first ? `Neprošlo: ${first.from} → ${first.to}${first.reason ? ` (${first.reason})` : ""}` : "Neprošlo: doklad nepokrývá všechny přechody";
  return { tone: "failed", text, ...meta };
}

/** Čas běhu pro člověka (místní čas, krátce); neplatný čas = prázdný text. */
export function verificationTime(at: string | null, locale = "cs-CZ", timeZone?: string): string {
  if (!at) return "";
  const moment = new Date(at);
  if (Number.isNaN(moment.getTime())) return "";
  return moment.toLocaleString(locale, { day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", ...(timeZone ? { timeZone } : {}) });
}

/** Popisek pro `title`: text odznaku, čas a příkaz, kterým doklad vznikl. */
export function verificationTitle(badge: VerificationBadge, timeZone?: string): string {
  const when = verificationTime(badge.at, "cs-CZ", timeZone);
  return [badge.text, when && `běh ${when}`, badge.command && `příkaz: ${badge.command}`].filter(Boolean).join(" · ");
}
