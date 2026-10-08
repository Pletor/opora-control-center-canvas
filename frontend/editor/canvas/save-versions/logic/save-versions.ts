// Uložené verze plátna (kontrakt docs/verze-platna.md). Čistá logika bez Reactu: jak se verze
// v seznamu jmenuje („Před 3 měsíci (21. 7. 12:32)“), co říká tlačítko ULOŽIT, kdo je autor a jak
// se pozná klávesa Ctrl+S. Komponenty ani hook nic z toho nepočítají samy.
import type { Workspace } from "@/shared/types/logic/types";

/** Jedna uložená verze, jak ji vrací `GET /api/canvas-versions` (nejnovější první). */
export type CanvasVersion = { id: string; createdAt: string; author: string; nodeCount: number; actor?: "agent" | "human" | "unknown"; changedCardCount?: number | null; coverage?: "full" | "legacy-partial"; unavailableAssets?: number };
/** Odpověď `GET /api/canvas-versions`: seznam verzí a jestli se plátno od poslední verze změnilo. */
export type CanvasVersions = { versions: CanvasVersion[]; dirty: boolean; currentToken?: string };

/** Autor, když aplikace nezná jméno ze svého profilu ani z pracovního prostoru. */
export const LOCAL_AUTHOR = "Místní uživatel";
const AUTHOR_LIMIT = 120;

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** Sedmý pád po „Před“: 1 → jednotné číslo, 2 a víc → množné (minutou / minutami, dnem / dny). */
const UNITS = {
  minute: ["minutou", "minutami"],
  hour: ["hodinou", "hodinami"],
  day: ["dnem", "dny"],
  month: ["měsícem", "měsíci"],
  year: ["rokem", "roky"],
} as const;

function before(count: number, unit: keyof typeof UNITS): string {
  const [one, many] = UNITS[unit];
  return `Před ${count} ${count === 1 ? one : many}`;
}

function toDate(value: string | Date): Date {
  return value instanceof Date ? value : new Date(value);
}

/**
 * Relativní čas česky: „Právě teď“ do minuty, pak minuty, hodiny, dny (do 30), měsíce (po 30 dnech,
 * nejvýš 11) a roky (po 365 dnech). Budoucí čas (posunuté hodiny) je také „Právě teď“.
 */
export function relativeTime(value: string | Date, now: Date = new Date()): string {
  const elapsed = now.getTime() - toDate(value).getTime();
  if (!Number.isFinite(elapsed) || elapsed < MINUTE) return "Právě teď";
  if (elapsed < HOUR) return before(Math.floor(elapsed / MINUTE), "minute");
  if (elapsed < DAY) return before(Math.floor(elapsed / HOUR), "hour");
  const days = Math.floor(elapsed / DAY);
  if (days < 30) return before(days, "day");
  if (days < 365) return before(Math.min(11, Math.floor(days / 30)), "month");
  return before(Math.floor(days / 365), "year");
}

/** Den, měsíc a čas v místním čase: „21. 7. 12:32“. */
export function clockLabel(value: string | Date): string {
  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getDate()}. ${date.getMonth() + 1}. ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Řádek verze v historii: „Před 3 měsíci (21. 7. 12:32)“. */
export function versionLabel(value: string | Date, now: Date = new Date()): string {
  const clock = clockLabel(value);
  return clock ? `${relativeTime(value, now)} (${clock})` : relativeTime(value, now);
}

/** Druhý řádek verze: „Autor: …“; prázdný autor je místní uživatel. */
export function authorLine(author: string): string {
  return `Autor: ${author.trim() || LOCAL_AUTHOR}`;
}

/**
 * Kdo verzi ukládá: vlastník otevřeného pracovního prostoru (zadaný při jeho vzniku), jinak místní
 * uživatel. Délka drží limit backendu (1..120 znaků).
 */
export function versionAuthor(workspaces: Workspace[] | undefined, workspaceId: string): string {
  const actor = workspaces?.find((item) => item.id === workspaceId)?.actor?.trim() ?? "";
  return (actor || LOCAL_AUTHOR).slice(0, AUTHOR_LIMIT);
}

/** Co tlačítko ULOŽIT právě říká: popisek, titulek a jestli má svítit (neuložené změny). */
export type SaveButtonView = { label: string; title: string; dirty: boolean };

export function saveButtonView(dirty: boolean, saving: boolean): SaveButtonView {
  if (saving) return { label: "Ukládám…", title: "Ukládám verzi plátna", dirty };
  return dirty
    ? { label: "ULOŽIT", title: "Změny nejsou uložené ve verzi", dirty: true }
    : { label: "ULOŽIT", title: "Plátno odpovídá poslední uložené verzi", dirty: false };
}

/** Po uložení nová verze nahoře, stejné ID se neopakuje; obnovit lze jen verzi, která v seznamu je. */
export function withSavedVersion(versions: CanvasVersion[], saved: CanvasVersion): CanvasVersion[] {
  return [saved, ...versions.filter((item) => item.id !== saved.id)];
}

export function canRestore(versions: CanvasVersion[], selectedId: string | null): boolean {
  return !!selectedId && versions.some((item) => item.id === selectedId);
}

/** Klávesa Ctrl+S (na Macu ⌘S) bez Altu a Shiftu: uložit verzi. */
export type SaveKey = { key: string; ctrlKey: boolean; metaKey: boolean; shiftKey: boolean; altKey: boolean };

export function isSaveShortcut(event: SaveKey): boolean {
  if (event.altKey || event.shiftKey) return false;
  if (!event.ctrlKey && !event.metaKey) return false;
  return event.key.toLowerCase() === "s";
}
