import { when, type LaidBall, type LaidCommit } from "./linie-board";

/**
 * Obsah bubliny při najetí (docs/navrhy/2026-11-06-linie-rebrand.md §10.1): kulička i kostka commitu mluví stejným
 * dílkem `LinieTip` – nadpis, řádky klíč · hodnota, patička „klik = detail“. `x`, `y` = bod na plátně, ke kterému se
 * bublina přichytí. Prázdné hodnoty se vynechají.
 */
export type TipRow = { k: string; v: string };
/** `hint` = patička místo „klik = detail“ (značka složené větve: „klik = rozbalit|složit“). */
export type Tip = { x: number; y: number; title: string; rows: TipRow[]; hint?: string };

const rows = (list: [string, string][]): TipRow[] => list.filter(([, v]) => v).map(([k, v]) => ({ k, v }));

export function ballTip(ball: LaidBall): Tip {
  const h = ball.hover;
  return { x: ball.x, y: ball.y, title: h.title, rows: rows([
    ["značka", h.mark], ["stav", ball.stateLabel], ["pravidlo", h.reason], ["další krok", h.next], ["začlení se do", h.target],
    ["vznik", h.created], ["začlenění", h.merged], ["commity|PR|merge", h.counts], ["větev", h.branch],
  ]) };
}

/** Tip kostky: `sha · zpráva`, čas, kulička, autor (agent posledního pokusu), zdroj; opuštěný říká, že do cíle nejde. */
export function commitTip(c: LaidCommit): Tip {
  return { x: c.x, y: c.y, title: c.title ? `${c.ref} · ${c.title}` : c.ref, rows: rows([
    ["čas", when(c.at)], ["kulička", [c.mark, c.ball].filter(Boolean).join(" ")], ["autor", c.agent || "—"], ["zdroj", "git log"],
    ["opuštěno", c.abandoned ? "zůstává v historii, do cíle nejde" : ""],
  ]) };
}
