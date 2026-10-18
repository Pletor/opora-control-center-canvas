// Jeden vstup sekce Duel jako v terminálu (docs/schranka-duel.md §4): druh výměny se vybírá slovem v textu, ne
// tlačítkem. Funkce z napsaného textu a kontextu (otevřený duel, fokus, představa) složí tělo POST /api/brief-vault,
// nebo vrátí srozumitelnou českou chybu; s chybou se nic neodešle. Pravidla duelu (mez tvrzení a kol, aktéři stran)
// hlídá server a jeho chybu ukáže vstup. Na výměnu se odkazuje krátkým číslem (#3 = třetí výměna v `duel.turns`,
// jak ji ukazuje stopa) i plným id; parser krátké číslo převede na plné id. Bez Reactu (test vedle).
import type { DuelTurn } from "./duel-view";

export type DuelContext = {
  project: string;
  scopeNodeId: string;
  /** Otevřený detail duelu; `null` = seznam (mimo duel). */
  duel: { fragmentId: string; revision: number; decided: boolean; turns: DuelTurn[]; humanSide: "A" | "B" | null } | null;
  /** Fragment fokusu Schránky s textem a revizí (subject duelu); `loading` = text se ještě načítá. */
  focus: { fragmentId: string; revision: number; text: string; discipline?: string | null } | { loading: true } | null;
  /** Text představy rozsahu (incumbent duelu o celém projektu); `null` = představa ještě není. */
  vision: string | null;
};

export type DuelCommand = { ok: true; body: Record<string, unknown>; label: string } | { ok: false; error: string };

export const TURN_MAX = 2000;
export const DIRECTION_MAX = 4000;
/** Poznámka revize představy (server ji vyžaduje). */
export const VISION_NOTE = "představa od člověka";
/** Jeden řádek nápovědy: čtyři nejčastější příkazy v duelu, nebo dva mimo něj. */
export const COMMAND_HELP = "A: / B: argument · ? otázka · odpověď #N: … · rozhodni";
export const OUTSIDE_HELP = "duel: co chceš změnit · představa: …";
/** Další příkazy (rozbalovací „další příkazy“ pod vstupem). */
export const MORE_COMMANDS: string[] = [
  "uznávám #N – strana uznává výměnu #N",
  "syntéza: … – spojení obou směrů za stranu, za kterou mluvíš",
  "skóre #N 0–10 A|B [doloženo] – hodnocení výměny",
  "rozhodni [#syntéza] [keep|adopt|synthesis: důvod] – rozhodnutí, případně přebití pravidla s důvodem",
  "sladění 0–10 #duel: poznámka – jak duel sedí s představou",
  "jiný text – poznámka do duelu",
  "mimo duel: duel: změna · představa: … · představa z duelu #id",
];
/** Příklad, jak se postavit za stranu (chyby ho ukazují místo suchého „napiš nejdřív A: nebo B:“). */
export const SIDE_EXAMPLE = "Napiš třeba: A: <tvůj argument>";

const fail = (error: string): DuelCommand => ({ ok: false, error });
const fold = (text: string) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase("cs");
const ID = "#([\\w-]+)";

/** Předpona s dvojtečkou bez ohledu na diakritiku a velikost („Syntéza:“ = „synteza:“); vrací zbytek textu. */
function after(text: string, word: string): string | null {
  const head = fold(text.slice(0, word.length + 1));
  return head === word + ":" ? text.slice(word.length + 1).trim() : null;
}

function tooLong(text: string, max: number): string | null {
  return text.length > max ? `Text je moc dlouhý (${text.length} znaků, nejvýš ${max}).` : null;
}

/** Id z původního textu (ne ze složeného bez diakritiky, id se nemění). */
const idIn = (text: string): string => text.match(new RegExp(ID))![1];

/** Odkaz na výměnu → plné id: přesná shoda id vyhrává, číslo N je N-tá výměna v `duel.turns`; jiné id projde
 * beze změny (ověří server). Číslo mimo rozsah = chyba. */
export function resolveTurn(ref: string, turns: DuelTurn[]): { id: string } | { error: string } {
  if (turns.some((turn) => turn.id === ref) || !/^\d+$/.test(ref)) return { id: ref };
  const turn = turns[Number(ref) - 1];
  if (turn) return { id: turn.id };
  return { error: turns.length ? `Výměna #${ref} tu není (výměny jsou #1–#${turns.length}).` : `Výměna #${ref} tu není, duel zatím nemá žádnou výměnu.` };
}

/** Krátké číslo výměny pro popisek („#3“), jinak id. */
function shortRef(id: string, turns: DuelTurn[]): string {
  const index = turns.findIndex((turn) => turn.id === id);
  return "#" + (index >= 0 ? index + 1 : id);
}

/** Strana, která odpovídá nebo uznává: opačná ke straně odkázané výměny, jinak ta, za kterou člověk mluví. */
function replySide(ctx: NonNullable<DuelContext["duel"]>, turnId: string): "A" | "B" | null {
  const turn = ctx.turns.find((item) => item.id === turnId);
  if (turn?.side === "A") return "B";
  if (turn?.side === "B") return "A";
  return ctx.humanSide;
}

export function parseDuelCommand(raw: string, ctx: DuelContext): DuelCommand {
  // NFC: složené znaky mají jednu pozici, takže předpona porovnaná bez diakritiky sedí na původní text.
  const text = raw.normalize("NFC").trim();
  if (!text) return fail("Napiš zprávu.");
  return visionCommand(text, ctx) ?? (ctx.duel ? inDuel(text, ctx.duel) : outside(text, ctx));
}

/** Představa a její sladění platí v seznamu i v duelu. */
function visionCommand(text: string, ctx: DuelContext): DuelCommand | null {
  const folded = fold(text);
  if (/^predstava\s+z\s+duelu\b/.test(folded)) {
    const found = new RegExp("^predstava\\s+z\\s+duelu\\s+" + ID + "\\s*$").exec(folded);
    if (!found) return fail("Převzetí představy piš jako „představa z duelu #<id duelu>“.");
    return { ok: true, label: "představa z duelu", body: { op: "vision-set", scopeNodeId: ctx.scopeNodeId, fromDuel: idIn(text), note: VISION_NOTE } };
  }
  if (/^sladeni\b/.test(folded)) {
    const found = new RegExp("^sladeni\\s+(\\d+(?:[.,]\\d+)?)\\s+" + ID + "\\s*:\\s*").exec(folded);
    if (!found) return fail("Sladění piš jako „sladění <0–10> #<id duelu>: poznámka“.");
    const score = Number(found[1].replace(",", "."));
    if (score > 10) return fail("Sladění s představou je 0–10.");
    const note = text.slice(found[0].length).trim();
    if (!note) return fail("Sladění potřebuje poznámku: „sladění 7 #<id>: proč“.");
    return { ok: true, label: "sladění s představou", body: { op: "vision-align", scopeNodeId: ctx.scopeNodeId, score, note, duelId: idIn(text) } };
  }
  const vision = after(text, "predstava");
  if (vision === null) return null;
  if (ctx.vision !== null) return fail("Představu mění jen rozhodnutý duel o projektu: „představa z duelu #<id>“.");
  if (!vision) return fail("Za „představa:“ chybí text.");
  return tooLong(vision, DIRECTION_MAX) ? fail(tooLong(vision, DIRECTION_MAX)!)
    : { ok: true, label: "představa", body: { op: "vision-set", scopeNodeId: ctx.scopeNodeId, text: vision, note: VISION_NOTE } };
}

function inDuel(text: string, duel: NonNullable<DuelContext["duel"]>): DuelCommand {
  if (duel.decided) return fail("Duel je rozhodnutý, další zápis nejde. Nový směr otevři ze seznamu příkazem „duel: …“.");
  const base = { fragmentId: duel.fragmentId, expectedRevision: duel.revision };
  const turn = (side: string, kind: string, body: string, refs?: string[], label = kind): DuelCommand => {
    if (!body) return fail("Za příkazem chybí text.");
    const long = tooLong(body, TURN_MAX);
    if (long) return fail(long);
    return { ok: true, label, body: { op: "duel-turn", ...base, side, kind, text: body, ...(refs ? { refs } : {}) } };
  };
  const folded = fold(text);

  const side = /^([ab])\s*:\s*([\s\S]*)$/i.exec(text);
  if (side) return turn(side[1].toUpperCase(), "claim", side[2].trim(), undefined, "tvrzení " + side[1].toUpperCase());

  if (text.startsWith("?")) {
    if (!duel.humanSide) return fail(`Za koho se ptáš? Nejdřív se postav za stranu. ${SIDE_EXAMPLE}, pak ? otázka.`);
    return turn(duel.humanSide, "grill", text.slice(1).trim(), undefined, "otázka za " + duel.humanSide);
  }

  const answer = new RegExp("^odpoved\\s+" + ID + "\\s*:\\s*").exec(folded);
  if (answer) {
    const ref = resolveTurn(idIn(text), duel.turns);
    if ("error" in ref) return fail(ref.error);
    const who = replySide(duel, ref.id);
    if (!who) return fail(`Neznám stranu odpovědi. ${SIDE_EXAMPLE}, nebo odpověz na výměnu strany: odpověď #1: …`);
    return turn(who, "answer", text.slice(answer[0].length).trim(), [ref.id], "odpověď na " + shortRef(ref.id, duel.turns));
  }
  if (/^odpoved\b/.test(folded)) return fail("Odpověď piš jako „odpověď #3: text“ (číslo výměny ze stopy).");

  const concede = new RegExp("^uznavam\\s+" + ID + "\\s*(?::\\s*)?").exec(folded);
  if (concede) {
    const ref = resolveTurn(idIn(text), duel.turns);
    if ("error" in ref) return fail(ref.error);
    const who = replySide(duel, ref.id);
    if (!who) return fail(`Neznám stranu, která uznává. ${SIDE_EXAMPLE}, nebo uznej výměnu strany: uznávám #1.`);
    const short = shortRef(ref.id, duel.turns);
    return turn(who, "concede", text.slice(concede[0].length).trim() || `Uznávám ${short}.`, [ref.id], "uznání " + short);
  }
  if (/^uznavam\b/.test(folded)) return fail("Uznání piš jako „uznávám #3“ (číslo výměny ze stopy).");

  const synthesis = after(text, "synteza");
  if (synthesis !== null) {
    // Strana human píše jen note (server, §2): syntézu podává strana, za kterou člověk mluví.
    if (!duel.humanSide) return fail(`Syntézu podává strana, za kterou mluvíš. ${SIDE_EXAMPLE}, pak syntéza: …`);
    return turn(duel.humanSide, "synthesis", synthesis, undefined, "syntéza za " + duel.humanSide);
  }

  if (/^skore\b/.test(folded)) {
    const score = new RegExp("^skore\\s+" + ID + "\\s+(\\d+(?:[.,]\\d+)?)\\s+([ab])(\\s+dolozeno)?\\s*$", "i").exec(folded);
    if (!score) return fail("Skóre piš jako „skóre #3 8 B“ (výměna, síla 0–10, strana), s dokladem „… doloženo“.");
    const strength = Number(score[2].replace(",", "."));
    if (strength > 10) return fail("Síla skóre musí být 0–10.");
    const ref = resolveTurn(idIn(text), duel.turns);
    if ("error" in ref) return fail(ref.error);
    return { ok: true, label: "skóre " + shortRef(ref.id, duel.turns), body: { op: "duel-score", ...base, turnId: ref.id, strength, supports: score[3].toUpperCase(),
      ...(score[4] ? { evidenceOk: true } : {}) } };
  }

  if (/^rozhodni\b/.test(folded)) return decide(text, folded, duel, base);

  return turn("human", "note", text, undefined, "poznámka");
}

/** `rozhodni` / `rozhodni #<syntéza>` / `rozhodni keep|adopt|synthesis [#<syntéza>]: důvod`. */
function decide(text: string, folded: string, duel: NonNullable<DuelContext["duel"]>, base: Record<string, unknown>): DuelCommand {
  const found = new RegExp("^rozhodni(?:\\s+(keep|adopt|synthesis))?(?:\\s+" + ID + ")?\\s*(:\\s*)?").exec(folded)!;
  const rest = text.slice(found[0].length).trim();
  const [, outcome, , colon] = found;
  if ((!outcome && (colon || rest)) || (outcome && !colon)) return fail("Rozhodnutí piš jako „rozhodni“, „rozhodni #<číslo syntézy>“, nebo „rozhodni keep|adopt|synthesis: důvod“.");
  const ref = found[2] ? resolveTurn(idIn(text), duel.turns) : null;
  if (ref && "error" in ref) return fail(ref.error);
  const turnId = ref ? ref.id : null;
  if (turnId && duel.turns.find((item) => item.id === turnId)?.kind !== "synthesis") return fail(`${shortRef(turnId, duel.turns)} není syntéza; rozhodni odkazuje na výměnu „syntéza: …“.`);
  if (outcome === "synthesis" && !turnId) return fail("Rozhodnutí syntézou potřebuje syntézu: „rozhodni synthesis #<číslo syntézy>: důvod“.");
  const chosen = turnId ? { synthesisTurnId: turnId } : {};
  if (!outcome) return { ok: true, label: "rozhodnutí", body: { op: "duel-decide", ...base, ...chosen } };
  if (!rest) return fail("Rozhodnutí mimo pravidlo potřebuje důvod: „rozhodni " + outcome + ": proč“.");
  const long = tooLong(rest, DIRECTION_MAX);
  if (long) return fail(long);
  return { ok: true, label: "rozhodnutí " + outcome, body: { op: "duel-decide", ...base, ...chosen, override: { outcome, reason: rest } } };
}

function outside(text: string, ctx: DuelContext): DuelCommand {
  const change = after(text, "duel");
  if (change === null) return fail("Mimo duel napiš „duel: změna směru“ nebo „představa: text“, nebo otevři duel ze seznamu.");
  if (!change) return fail("Za „duel:“ chybí text změny.");
  const long = tooLong(change, DIRECTION_MAX);
  if (long) return fail(long);
  const focus = ctx.focus;
  if (focus && "loading" in focus) return fail("Načítám text fragmentu ve fokusu, zkus to za chvíli.");
  if (focus) {
    return { ok: true, label: "duel o fragmentu", body: { op: "duel-open", scopeNodeId: ctx.scopeNodeId,
      subject: { kind: "fragment", id: focus.fragmentId },
      incumbent: { text: focus.text.slice(0, DIRECTION_MAX), ref: { fragmentId: focus.fragmentId, revision: focus.revision } },
      challenger: { text: change }, ...(focus.discipline ? { discipline: focus.discipline } : {}) } };
  }
  if (!ctx.vision) return fail("Bez fragmentu ve fokusu jde duel o celý projekt proti představě; nejdřív ji zapiš: „představa: …“.");
  return { ok: true, label: "duel o projektu", body: { op: "duel-open", scopeNodeId: ctx.scopeNodeId,
    subject: { kind: "project", id: ctx.project }, incumbent: { text: ctx.vision.slice(0, DIRECTION_MAX) }, challenger: { text: change } } };
}
