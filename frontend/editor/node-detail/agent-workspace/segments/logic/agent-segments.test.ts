import { describe, expect, it } from "vitest";
import { SECTIONS } from "@/editor/node-detail/agent-workspace/logic/agent-workspace";
import {
  SEGMENTS,
  SEGMENT_PREFS_KEY,
  collapseAll,
  defaultOpen,
  expandAll,
  mergeOpen,
  parseSegmentPrefs,
  readSegmentPrefs,
  segmentId,
  writeSegmentPrefs,
  type SegmentId,
  type SegmentStorage,
} from "./agent-segments";

const ORDER: SegmentId[] = [
  "overview", "orientation", "communication", "memory", "frame", "log", "failures", "fixes", "handoff",
];

/** Úložiště jako obyčejný objekt: test nikdy nesahá na globální localStorage. */
function fakeStorage(seed: Record<string, string> = {}): SegmentStorage & { data: Record<string, string> } {
  const data = { ...seed };
  return {
    data,
    getItem: (key: string) => (key in data ? data[key] : null),
    setItem: (key: string, value: string) => { data[key] = value; },
  };
}

function brokenStorage(): SegmentStorage {
  return {
    getItem: () => { throw new Error("úložiště není dostupné"); },
    setItem: () => { throw new Error("úložiště není dostupné"); },
  };
}

describe("agent-segments: pořadí a popisky", () => {
  it("SEGMENTS drží devět segmentů v pevném pořadí", () => {
    expect(SEGMENTS.map((s) => s.id)).toEqual(ORDER);
  });

  it("Paměť role stojí hned za Komunikací a bere si celou šířku mřížky", () => {
    const memory = SEGMENTS.find((s) => s.id === "memory");
    expect(SEGMENTS.findIndex((s) => s.id === "memory")).toBe(SEGMENTS.findIndex((s) => s.id === "communication") + 1);
    expect(memory?.title).toBe("Paměť role");
    expect(memory?.area).toBe("top");
    expect(memory?.wide).toBe(true);
  });

  it("popisek Paměti role přizná, že se čte a zapisuje jen na pokyn člověka", () => {
    expect(SEGMENTS.find((s) => s.id === "memory")?.caption).toBe(
      "Zkušenosti role napříč projekty a detail této karty; čte a zapisuje jen na tvůj pokyn.",
    );
  });

  it("každý segment má titulek a jednu větu popisku", () => {
    for (const segment of SEGMENTS) {
      expect(segment.title.length).toBeGreaterThan(0);
      expect(segment.caption.length).toBeGreaterThan(0);
    }
  });

  it("oblasti jsou přehled, horní trojice a pět polí paměti karty", () => {
    expect(SEGMENTS.filter((s) => s.area === "overview").map((s) => s.id)).toEqual(["overview"]);
    expect(SEGMENTS.filter((s) => s.area === "top").map((s) => s.id)).toEqual(["orientation", "communication", "memory"]);
    expect(SEGMENTS.filter((s) => s.area === "memory").map((s) => s.id)).toEqual(SECTIONS.map((s) => s.key));
  });

  it("pole paměti nesou stejné titulky jako sekce prostoru", () => {
    const memory = SEGMENTS.filter((s) => s.area === "memory");
    expect(memory.map((s) => s.title)).toEqual(SECTIONS.map((s) => s.label));
  });

  it("popisek komunikace řekne, kdo sem píše a kam vedou čísla z přehledu", () => {
    const communication = SEGMENTS.find((s) => s.id === "communication");
    expect(communication?.caption).toBe("Zprávy adresované této kartě; čísla v Přehledu vedou sem.");
  });

  it("popisek každého pole paměti přizná, že jde o poznámky modelu, ne o zadání", () => {
    for (const segment of SEGMENTS.filter((s) => s.area === "memory")) {
      expect(segment.caption.toLowerCase()).toContain("poznámky modelu");
      expect(segment.caption.toLowerCase()).toContain("ne zadání");
    }
  });

  it("segmentId složí kotvu s ID karty, aby dvě karty na ploše nesdílely jedno id", () => {
    expect(segmentId("node-1", "communication")).toBe("agent-seg-node-1-communication");
    expect(segmentId("sektor-2", "frame")).toBe("agent-seg-sektor-2-frame");
  });
});

describe("agent-segments: výchozí rozbalení", () => {
  it("bez znalosti paměti jsou otevřené přehled, start a komunikace; paměť role zůstane zavřená", () => {
    expect(defaultOpen()).toEqual({
      overview: true, orientation: true, communication: true, memory: false,
      frame: false, log: false, failures: false, fixes: false, handoff: false,
    });
  });

  it("paměť role se sama neotevře ani u karty, která má co v polích paměti", () => {
    expect(defaultOpen({ frame: true, log: true }).memory).toBe(false);
  });

  it("pole paměti, které už něco nese, se otevře samo", () => {
    expect(defaultOpen({ frame: true, handoff: true })).toMatchObject({
      frame: true, handoff: true, log: false, failures: false, fixes: false,
    });
  });

  it("expandAll otevře všech devět, collapseAll zavře vše kromě přehledu", () => {
    expect(Object.values(expandAll()).every(Boolean)).toBe(true);
    const collapsed = collapseAll();
    expect(collapsed.overview).toBe(true);
    expect(ORDER.filter((id) => id !== "overview").every((id) => collapsed[id] === false)).toBe(true);
  });
});

describe("agent-segments: uložená preference", () => {
  it("prázdný, rozbitý i cizí tvar skončí bez preference", () => {
    expect(parseSegmentPrefs(null)).toEqual({ open: {} });
    expect(parseSegmentPrefs("")).toEqual({ open: {} });
    expect(parseSegmentPrefs("{nevalidní")).toEqual({ open: {} });
    expect(parseSegmentPrefs("[1,2,3]")).toEqual({ open: {} });
    expect(parseSegmentPrefs('"text"')).toEqual({ open: {} });
    expect(parseSegmentPrefs('{"open":"ne"}')).toEqual({ open: {} });
  });

  it("neznámé klíče a nebooleovské hodnoty se zahodí", () => {
    expect(parseSegmentPrefs('{"open":{"frame":true,"vymyslene":true,"log":"ano"}}')).toEqual({
      open: { frame: true },
    });
  });

  it("uložené hodnoty se přečtou i pro zavřený segment", () => {
    expect(parseSegmentPrefs('{"open":{"communication":false,"handoff":true}}')).toEqual({
      open: { communication: false, handoff: true },
    });
  });

  it("readSegmentPrefs čte pod jediným klíčem aplikace", () => {
    const storage = fakeStorage({ [SEGMENT_PREFS_KEY]: '{"open":{"log":true}}' });
    expect(readSegmentPrefs(storage)).toEqual({ open: { log: true } });
  });

  it("chybějící i padající úložiště vrátí prázdnou preferenci", () => {
    expect(readSegmentPrefs(null)).toEqual({ open: {} });
    expect(readSegmentPrefs(brokenStorage())).toEqual({ open: {} });
  });

  it("writeSegmentPrefs uloží JSON pod klíč a řekne, že se zapsalo", () => {
    const storage = fakeStorage();
    expect(writeSegmentPrefs(storage, { open: { frame: true } })).toBe(true);
    expect(JSON.parse(storage.data[SEGMENT_PREFS_KEY])).toEqual({ open: { frame: true } });
  });

  it("zápis bez úložiště nic neshodí, jen se neuloží", () => {
    expect(writeSegmentPrefs(null, { open: {} })).toBe(false);
    expect(writeSegmentPrefs(brokenStorage(), { open: {} })).toBe(false);
  });

  it("uloží se jen známé segmenty, aby klíč nerostl cizími daty", () => {
    const storage = fakeStorage();
    writeSegmentPrefs(storage, { open: { frame: true, smysl: true } as Record<string, boolean> });
    expect(JSON.parse(storage.data[SEGMENT_PREFS_KEY])).toEqual({ open: { frame: true } });
  });

  it("zapsaná preference se přečte zpátky beze změny", () => {
    const storage = fakeStorage();
    writeSegmentPrefs(storage, { open: collapseAll() });
    expect(readSegmentPrefs(storage).open).toEqual(collapseAll());
  });
});

describe("agent-segments: složení výchozího stavu a preference", () => {
  it("bez uložené preference platí výchozí stav", () => {
    expect(mergeOpen(defaultOpen({ frame: true }), { open: {} })).toEqual(defaultOpen({ frame: true }));
  });

  it("uložená preference přebíjí výchozí stav v obou směrech", () => {
    const merged = mergeOpen(defaultOpen(), { open: { communication: false, handoff: true } });
    expect(merged.communication).toBe(false);
    expect(merged.handoff).toBe(true);
    expect(merged.orientation).toBe(true);
  });

  it("přehled zůstane otevřený, i kdyby ho preference zavírala — není sbalitelný", () => {
    expect(mergeOpen(defaultOpen(), { open: { overview: false } }).overview).toBe(true);
    expect(mergeOpen(collapseAll(), { open: {} }).overview).toBe(true);
  });

  it("uložená preference umí paměť role otevřít i zavřít", () => {
    expect(mergeOpen(defaultOpen(), { open: { memory: true } }).memory).toBe(true);
    expect(mergeOpen(defaultOpen(), { open: {} }).memory).toBe(false);
  });

  it("výsledek má vždy všech devět klíčů", () => {
    expect(Object.keys(mergeOpen(defaultOpen(), { open: {} })).sort()).toEqual([...ORDER].sort());
  });
});
