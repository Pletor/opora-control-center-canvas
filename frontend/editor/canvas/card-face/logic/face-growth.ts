// Růst karty na plátně 3 (docs/navrhy/2026-11-11-platno-3-folie.md, F3 a „Plátno“): tvar rámečku, kruh postupu,
// čtyři tečky pravd Z/K/S/B a živý pulz. Jen odvozeno z hotové tváře (agent-state) a záměru karty; nic se nedotahuje.
import type { CardFace } from "./card-face";

/** seed = jen záměr, bud = Kancelář staví, leaf = doloženo, prop = návrh čeká na přijetí.
 *  shortcut: „dry“ (slepá cesta) zatím nemá v datech signál; až ho agent-state ponese, přidá se sem. */
export type GrowthShape = "seed" | "bud" | "leaf" | "prop";
/** ok platí · miss neplatí · wait neměří se · part zrcadlo sedí zčásti · bad zrcadlo rozporuje kartě. */
export type TruthMark = "ok" | "miss" | "wait" | "part" | "bad";
export type FaceGrowth = {
  shape: GrowthShape; label: string;
  /** Podíl hotových kroků 0–100; karta bez kroků `null` (kruh ukáže „—“, ne falešnou nulu). */
  percent: number | null;
  /** Z záměr · K zrcadlo kódu (F1) · S skutečnost v main · B budoucnost po sloučení (F4). */
  truths: [TruthMark, TruthMark, TruthMark, TruthMark];
  /** Kartu právě drží běžící lease nebo exekuce. */
  live: boolean;
};

const LABEL: Record<GrowthShape, string> = { seed: "semínko", bud: "vývoj", leaf: "doloženo", prop: "návrh" };
/** Stejná množina jako osa „Realizace“ v `node-card/logic/progress-axes.ts`: sloučeno do main. */
const MERGED = new Set(["plan_written_back", "card_closed", "awaiting_human_close"]);
/** Neznámá hodnota zrcadla se bere jako neměřená, ne jako shoda. */
const mirrorMark = (mirror: string | null): TruthMark => mirror === "ok" || mirror === "part" || mirror === "bad" ? mirror : "wait";
/** Verdikt budoucnosti: čisté = ok, dopady nebo překryvy = zčásti, konflikt = rozpor; jinak neměřeno. */
const FUTURE: Record<string, TruthMark> = { clean: "ok", warning: "part", blocked: "bad" };

export function faceGrowth(face: CardFace, purpose: string): FaceGrowth {
  const shape: GrowthShape = face.state === "done" ? "leaf"
    : face.raw.stage === "proposal" ? "prop"
    : face.state === "working" || face.state === "review" || face.state === "decision" ? "bud" : "seed";
  const { total, done } = face.steps;
  const percent = face.state === "done" ? 100 : total ? Math.round((done / total) * 100) : null;
  const intent = !!purpose.trim() || total > 0;
  return {
    shape, label: LABEL[shape], percent,
    truths: [intent ? "ok" : "miss", mirrorMark(face.raw.mirror), MERGED.has(face.raw.reason) ? "ok" : "miss",
      FUTURE[face.raw.future ?? ""] ?? "wait"],
    live: !!face.lease || (face.raw.stage === "work" && !!face.raw.executionId),
  };
}
