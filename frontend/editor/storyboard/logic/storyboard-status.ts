// Text štítku stavu v liště storyboardu bez Reactu: neuloženo / ukládám / uloženo v čase a kolik komentářů čeká na agenta.
import type { StoryboardStatus } from "./use-storyboard-store";

export type StatusTone = "quiet" | "dirty" | "warn";

/** „1 komentář čeká“, „2 komentáře čekají“, „5 komentářů čeká“ (česká shoda podmětu s přísudkem). */
export function commentsWaiting(n: number): string {
  if (n === 1) return "1 komentář čeká na agenta";
  if (n >= 2 && n <= 4) return `${n} komentáře čekají na agenta`;
  return `${n} komentářů čeká na agenta`;
}

/** Čas posledního uložení jako HH:MM v místním čase. */
export function clockTime(at: Date): string {
  return `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
}

export function statusLabel(s: {
  status: StoryboardStatus;
  dirty: boolean;
  /** Koncept se uloží sám (platný a ne jen ke čtení). */
  autosave: boolean;
  /** Chyba ze serveru nebo první chyba `validate`. */
  message: string;
  savedAt: Date | null;
  openComments: number;
}): { text: string; tone: StatusTone } {
  const why = s.message ? ": " + s.message : "";
  if (s.status === "saving") return { text: "Ukládám…", tone: "quiet" };
  if (s.status === "conflict") return { text: "Změněno jinde" + why, tone: "warn" };
  if (s.status === "error") return { text: "Chyba" + why, tone: "warn" };
  if (s.status === "loading") return { text: "Načítám…", tone: "quiet" };
  if (s.dirty) return s.autosave ? { text: "Neuloženo · ukládám za chvíli", tone: "dirty" } : { text: "Neuloženo" + why, tone: s.message ? "warn" : "dirty" };
  const saved = s.savedAt ? "Uloženo " + clockTime(s.savedAt) : "Uloženo";
  return { text: s.openComments > 0 ? `${saved} · ${commentsWaiting(s.openComments)}` : saved, tone: "quiet" };
}
