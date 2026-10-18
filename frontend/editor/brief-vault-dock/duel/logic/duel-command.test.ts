import { describe, expect, it } from "vitest";
import { parseDuelCommand, type DuelContext } from "./duel-command";
import type { DuelTurn } from "./duel-view";

const turns: DuelTurn[] = [
  { id: "t1", side: "B", kind: "claim", text: "B je rychlejší", actor: "agent" },
  { id: "t2", side: "A", kind: "grill", text: "Kde je důkaz?", actor: "agent" },
];
const inDuel = (extra: Partial<NonNullable<DuelContext["duel"]>> = {}): DuelContext => ({
  project: "p", scopeNodeId: "s", focus: null, vision: null,
  duel: { fragmentId: "d1", revision: 3, decided: false, turns, humanSide: null, ...extra },
});
const outside = (extra: Partial<DuelContext> = {}): DuelContext => ({ project: "p", scopeNodeId: "s", duel: null, focus: null, vision: null, ...extra });
const body = (text: string, ctx: DuelContext) => {
  const result = parseDuelCommand(text, ctx);
  if (!result.ok) throw new Error(result.error);
  return result.body;
};
const error = (text: string, ctx: DuelContext) => {
  const result = parseDuelCommand(text, ctx);
  if (result.ok) throw new Error("čekal jsem chybu");
  return result.error;
};

describe("duel command", () => {
  it("A: / B: is a claim of the side with CAS revision", () => {
    expect(body("A: starý směr drží", inDuel())).toEqual({ op: "duel-turn", fragmentId: "d1", expectedRevision: 3, side: "A", kind: "claim", text: "starý směr drží" });
    expect(body("b:  nový\nřádek", inDuel())).toMatchObject({ side: "B", kind: "claim", text: "nový\nřádek" });
  });

  it("? is a grill for the side the human speaks for, otherwise an error", () => {
    expect(error("? proč", inDuel())).toContain("Napiš třeba: A: <tvůj argument>");
    expect(body("? proč", inDuel({ humanSide: "B" }))).toMatchObject({ side: "B", kind: "grill", text: "proč" });
  });

  it("answer and concede reply for the side opposite to the referenced turn", () => {
    expect(body("odpověď #t2: tady je odkaz", inDuel())).toMatchObject({ side: "B", kind: "answer", refs: ["t2"], text: "tady je odkaz" });
    expect(body("Odpoved #t2: bez diakritiky", inDuel())).toMatchObject({ kind: "answer", refs: ["t2"] });
    expect(body("uznávám #t1", inDuel())).toMatchObject({ side: "A", kind: "concede", refs: ["t1"], text: "Uznávám #1." });
    expect(error("odpověď #x9: text", inDuel())).toContain("Neznám stranu");
    expect(body("odpověď #x9: text", inDuel({ humanSide: "A" }))).toMatchObject({ side: "A" });
    expect(error("odpověď bez id", inDuel())).toContain("odpověď #3:");
  });

  it("synthesis, note, score and decide", () => {
    expect(error("syntéza: obojí", inDuel())).toContain("Napiš třeba: A: <tvůj argument>");
    expect(body("Syntéza: za B", inDuel({ humanSide: "B" }))).toMatchObject({ side: "B", kind: "synthesis" });
    expect(body("prostě poznámka", inDuel())).toMatchObject({ side: "human", kind: "note", text: "prostě poznámka" });
    expect(body("skóre #t1 7 B", inDuel())).toEqual({ op: "duel-score", fragmentId: "d1", expectedRevision: 3, turnId: "t1", strength: 7, supports: "B" });
    expect(body("skore #t1 6,5 a", inDuel())).toMatchObject({ strength: 6.5, supports: "A" });
    expect(error("skóre #t1 11 B", inDuel())).toContain("0–10");
    expect(error("skóre t1", inDuel())).toContain("skóre #3 8 B");
    expect(body("skóre #t1 8 B doloženo", inDuel())).toMatchObject({ op: "duel-score", turnId: "t1", strength: 8, supports: "B", evidenceOk: true });
    expect(body("skóre #t1 8 B", inDuel())).not.toHaveProperty("evidenceOk");
    expect(body("rozhodni", inDuel())).toEqual({ op: "duel-decide", fragmentId: "d1", expectedRevision: 3 });
    const withSynthesis = inDuel({ turns: [...turns, { id: "t3", side: "A", kind: "synthesis", text: "S", actor: "agent" }] });
    expect(body("rozhodni #t3", withSynthesis)).toEqual({ op: "duel-decide", fragmentId: "d1", expectedRevision: 3, synthesisTurnId: "t3" });
    expect(error("rozhodni #t1", withSynthesis)).toContain("není syntéza");
    expect(body("rozhodni synthesis #t3: obě půlky platí", withSynthesis)).toEqual({ op: "duel-decide", fragmentId: "d1", expectedRevision: 3,
      synthesisTurnId: "t3", override: { outcome: "synthesis", reason: "obě půlky platí" } });
    expect(error("rozhodni synthesis: bez syntézy", inDuel())).toContain("#<číslo syntézy>");
    expect(error("rozhodni keep", inDuel())).toContain("rozhodni keep|adopt|synthesis");
    expect(body("rozhodni keep: B nemá doklad", inDuel())).toEqual({ op: "duel-decide", fragmentId: "d1", expectedRevision: 3,
      override: { outcome: "keep", reason: "B nemá doklad" } });
    expect(error("rozhodni adopt:", inDuel())).toContain("důvod");
    expect(error("rozhodni hned", inDuel())).toContain("rozhodni keep|adopt|synthesis");
  });

  it("short turn numbers #N resolve to the full id in duel.turns order", () => {
    expect(body("odpověď #2: tady", inDuel())).toMatchObject({ side: "B", kind: "answer", refs: ["t2"] });
    expect(body("uznávám #1", inDuel())).toMatchObject({ side: "A", kind: "concede", refs: ["t1"], text: "Uznávám #1." });
    expect(body("skóre #2 8 B", inDuel())).toMatchObject({ op: "duel-score", turnId: "t2", strength: 8, supports: "B" });
    expect(parseDuelCommand("odpověď #2: x", inDuel())).toMatchObject({ ok: true, label: "odpověď na #2" });
    const withSynthesis = inDuel({ turns: [...turns, { id: "f00d", side: "A", kind: "synthesis", text: "S", actor: "agent" }] });
    expect(body("rozhodni #3", withSynthesis)).toMatchObject({ op: "duel-decide", synthesisTurnId: "f00d" });
    expect(error("rozhodni #1", withSynthesis)).toBe("#1 není syntéza; rozhodni odkazuje na výměnu „syntéza: …“.");
    expect(error("odpověď #9: x", inDuel())).toBe("Výměna #9 tu není (výměny jsou #1–#2).");
    expect(error("skóre #1 5 A", inDuel({ turns: [] }))).toContain("nemá žádnou výměnu");
    // Plné id dál platí a přesná shoda id má přednost před číslem.
    expect(body("skóre #t1 5 A", inDuel())).toMatchObject({ turnId: "t1" });
    const numeric = inDuel({ turns: [{ id: "2", side: "A", kind: "claim", text: "", actor: "agent" }, { id: "x", side: "B", kind: "claim", text: "", actor: "agent" }] });
    expect(body("uznávám #2", numeric)).toMatchObject({ refs: ["2"] });
  });

  it("refuses empty, too long and decided", () => {
    expect(error("   ", inDuel())).toBe("Napiš zprávu.");
    expect(error("A: ", inDuel())).toContain("chybí text");
    expect(error("A: " + "x".repeat(2001), inDuel())).toContain("nejvýš 2000");
    expect(error("A: cokoli", inDuel({ decided: true }))).toContain("rozhodnutý");
  });

  it("outside a duel opens one about the focus fragment, or about the project against the vision", () => {
    const focus = { fragmentId: "f1", revision: 4, text: "Starý text", discipline: "be" };
    expect(body("duel: nový směr", outside({ focus }))).toEqual({ op: "duel-open", scopeNodeId: "s", subject: { kind: "fragment", id: "f1" },
      incumbent: { text: "Starý text", ref: { fragmentId: "f1", revision: 4 } }, challenger: { text: "nový směr" }, discipline: "be" });
    expect(body("Duel: celý projekt jinak", outside({ vision: "Představa" }))).toEqual({ op: "duel-open", scopeNodeId: "s",
      subject: { kind: "project", id: "p" }, incumbent: { text: "Představa" }, challenger: { text: "celý projekt jinak" } });
    expect(error("duel: x", outside())).toContain("představa:");
    expect(error("duel: x", outside({ focus: { loading: true } }))).toContain("Načítám");
    expect(error("duel:", outside())).toContain("chybí text");
    expect(body("představa: aplikace řídí agenty", outside())).toEqual({ op: "vision-set", scopeNodeId: "s", text: "aplikace řídí agenty", note: "představa od člověka" });
    expect(body("predstava: bez diakritiky", outside())).toMatchObject({ op: "vision-set", text: "bez diakritiky" });
    expect(error("představa: nová", outside({ vision: "stará" }))).toBe("Představu mění jen rozhodnutý duel o projektu: „představa z duelu #<id>“.");
    expect(body("představa z duelu #d7", outside({ vision: "stará" }))).toEqual({ op: "vision-set", scopeNodeId: "s", fromDuel: "d7", note: "představa od člověka" });
    expect(error("představa z duelu d7", outside())).toContain("#<id duelu>");
    expect(body("sladění 7 #d7: směr sedí", inDuel())).toEqual({ op: "vision-align", scopeNodeId: "s", score: 7, note: "směr sedí", duelId: "d7" });
    expect(body("sladeni 6,5 #d7: ok", outside())).toMatchObject({ op: "vision-align", score: 6.5 });
    expect(error("sladění 11 #d7: x", outside())).toContain("0–10");
    expect(error("sladění 7 #d7:", outside())).toContain("poznámku");
    expect(error("sladění 7", outside())).toContain("sladění <0–10>");
    expect(error("A: argument", outside())).toContain("Mimo duel");
  });

  it("accepts decomposed (NFD) diacritics", () => {
    expect(body("odpověď #t2: ok".normalize("NFD"), inDuel())).toMatchObject({ kind: "answer", text: "ok" });
  });
});
