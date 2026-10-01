// Rozložení záložky Agenti na pojmenované segmenty: co je za celek, jak se jmenuje, k čemu slouží
// a jestli je právě rozbalený. Modul je čistý — nic nenačítá, nic nekreslí a nesahá na globální
// `localStorage`: úložiště dostává v argumentu, takže stejná pravidla platí v prohlížeči i v testu.
// Rozbalení je vzhled, ne obsah karty, proto se ukládá jednou pro celou aplikaci pod jediným klíčem
// (viz „Jedno rozhraní pro všechny projekty“ v docs/pravidla-struktury.md), nikdy s ID projektu.
import { SECTIONS, type SectionKey } from "@/editor/node-detail/agent-workspace/logic/agent-workspace";

/** Segment = jeden pojmenovaný celek plochy. Pořadí je pevné: přehled, horní trojice, pět polí paměti. */
export type SegmentId = "overview" | "orientation" | "communication" | "memory" | SectionKey;

/** Kde segment na ploše stojí: pás přes celou šířku, horní trojice, nebo sloupec paměti karty. */
export type SegmentArea = "overview" | "top" | "memory";

export type SegmentDef = {
  id: SegmentId;
  title: string;
  caption: string;
  area: SegmentArea;
  /** Jak segment stojí u nové karty, než si člověk nastaví své; pole paměti to ještě upřesní obsahem. */
  startsOpen: boolean;
  /** Horní segment, který se do poloviny řádku nevejde, a tak si bere celou šířku mřížky. */
  wide?: boolean;
};

/** Popisky polí paměti mluví jazykem kontraktu: prostor patří modelu, člověk se dívá přes rameno. */
const MEMORY_CAPTIONS: Record<SectionKey, string> = {
  frame: "Kam práce míří a kudy tam vede cesta; poznámky modelu k této kartě, ne zadání.",
  log: "Co už se na kartě udělalo, krok po kroku; poznámky modelu k této kartě, ne zadání.",
  failures: "Slepé uličky, aby je další agent neopakoval; poznámky modelu k této kartě, ne zadání.",
  fixes: "Co se pokazilo a čím se to spravilo; poznámky modelu k této kartě, ne zadání.",
  handoff: "Kudy pokračovat a kam se podívat dál; poznámky modelu k této kartě, ne zadání.",
};

/** Devět segmentů plochy v pořadí, ve kterém je člověk i model čte. Titulky paměti drží `SECTIONS`. */
export const SEGMENTS: SegmentDef[] = [
  {
    id: "overview",
    title: "Přehled",
    caption: "Stav karty na jeden pohled; čísla a dlaždice odtud vedou do ostatních segmentů.",
    area: "overview",
    startsOpen: true,
  },
  {
    id: "orientation",
    title: "Start pro agenta",
    caption: "Co si přečíst, než začneš; čte se z právě načteného briefu karty.",
    area: "top",
    startsOpen: true,
  },
  {
    id: "communication",
    title: "Komunikace",
    caption: "Zprávy adresované této kartě; čísla v Přehledu vedou sem.",
    area: "top",
    startsOpen: true,
  },
  {
    id: "memory",
    title: "Paměť role",
    caption: "Zkušenosti role napříč projekty a detail této karty; čte a zapisuje jen na tvůj pokyn.",
    area: "top",
    // Zavřená napoprvé: paměť role se ptá cizí služby, a to je krok, o kterém má rozhodnout člověk.
    startsOpen: false,
    wide: true,
  },
  ...SECTIONS.map(({ key, label }): SegmentDef => ({
    id: key,
    title: label,
    caption: MEMORY_CAPTIONS[key],
    area: "memory",
    startsOpen: false,
  })),
];

const IDS: SegmentId[] = SEGMENTS.map((segment) => segment.id);
const KNOWN = new Set<string>(IDS);

/** Segment, který se nikdy nesbalí: bez přehledu by plocha ztratila jediné místo, odkud se orientuje. */
export const ALWAYS_OPEN: SegmentId = "overview";

/** Jediný klíč pro celou aplikaci. Nikdy se do něj nepřidává id projektu ani karty. */
export const SEGMENT_PREFS_KEY = "opora:agent-segments:v1";

export type SegmentOpen = Record<SegmentId, boolean>;

/** Uložená preference je vždy jen část mapy: co v ní není, rozhoduje výchozí stav karty. */
export type SegmentPrefs = { open: Partial<Record<SegmentId, boolean>> };

/** Jen ta část úložiště, na které pravidlo stojí — v testu ji zastoupí obyčejný objekt. */
export type SegmentStorage = {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
};

/** HTML id segmentu jedné karty; ID karty je v něm proto, aby dvě karty na ploše nesdílely kotvu. */
export function segmentId(nodeId: string, id: SegmentId): string {
  return `agent-seg-${nodeId}-${id}`;
}

/**
 * Výchozí stav plochy: přehled, start a komunikace otevřené (to je to, čím se karta otevírá),
 * paměť role zavřená (ta se ptá cizí služby) a pole paměti karty jen ta, která už něco nesou —
 * prázdné pole zůstane tiché, stejně jako v inspektoru.
 */
export function defaultOpen(memory: Partial<Record<SectionKey, boolean>> = {}): SegmentOpen {
  const open = {} as SegmentOpen;
  for (const segment of SEGMENTS) open[segment.id] = segment.startsOpen;
  for (const { key } of SECTIONS) open[key] = memory[key] === true;
  return open;
}

export function expandAll(): SegmentOpen {
  const open = {} as SegmentOpen;
  for (const id of IDS) open[id] = true;
  return open;
}

/** Sbalit vše nechá přehled otevřený: není sbalitelný, tak ho tlačítko nesmí zavřít. */
export function collapseAll(): SegmentOpen {
  const open = {} as SegmentOpen;
  for (const id of IDS) open[id] = id === ALWAYS_OPEN;
  return open;
}

/** Uložená preference je cizí text: co nesedí na známý segment a boolean, se tiše zahodí. */
export function parseSegmentPrefs(raw: string | null): SegmentPrefs {
  const empty: SegmentPrefs = { open: {} };
  if (!raw) return empty;
  try {
    const value = JSON.parse(raw) as unknown;
    if (!value || typeof value !== "object" || Array.isArray(value)) return empty;
    const stored = (value as { open?: unknown }).open;
    if (!stored || typeof stored !== "object" || Array.isArray(stored)) return empty;
    const open: SegmentPrefs["open"] = {};
    for (const [key, flag] of Object.entries(stored as Record<string, unknown>)) {
      if (KNOWN.has(key) && typeof flag === "boolean") open[key as SegmentId] = flag;
    }
    return { open };
  } catch {
    return empty;
  }
}

/** Čtení preference; prohlížeč bez úložiště (soukromé okno, test) dostane prázdnou preferenci. */
export function readSegmentPrefs(storage: SegmentStorage | null): SegmentPrefs {
  if (!storage) return { open: {} };
  try {
    return parseSegmentPrefs(storage.getItem(SEGMENT_PREFS_KEY));
  } catch {
    return { open: {} };
  }
}

/** Zápis preference nikdy neshodí plochu: když úložiště není, jen se nic neuloží. */
export function writeSegmentPrefs(storage: SegmentStorage | null, prefs: SegmentPrefs): boolean {
  if (!storage) return false;
  const open: SegmentPrefs["open"] = {};
  for (const [key, flag] of Object.entries(prefs.open)) {
    if (KNOWN.has(key) && typeof flag === "boolean") open[key as SegmentId] = flag;
  }
  try {
    storage.setItem(SEGMENT_PREFS_KEY, JSON.stringify({ open }));
    return true;
  } catch {
    return false;
  }
}

/** Výchozí stav karty doplněný o to, co si uživatel naposledy nastavil; přehled zůstává otevřený. */
export function mergeOpen(defaults: SegmentOpen, stored: SegmentPrefs): SegmentOpen {
  const open = {} as SegmentOpen;
  for (const id of IDS) {
    const preference = stored.open[id];
    open[id] = typeof preference === "boolean" ? preference : defaults[id] === true;
  }
  open[ALWAYS_OPEN] = true;
  return open;
}
