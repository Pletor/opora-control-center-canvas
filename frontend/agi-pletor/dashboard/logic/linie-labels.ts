/**
 * Kolize popisků kuliček (docs/navrhy/2026-11-06-linie-rebrand.md §6, §10.1): kulička se v čase nikdy neposune, uhýbá
 * jen její popisek. Přednost má vybraná kulička, pak se zkouší pod · nad · druhé patro pod · druhé patro nad (řádek
 * s pruhy worktree jen nad osou); slot je volný, když v něm žádný popisek neleží blíž než GAP. Kdo se nevejde ani do
 * dvou pater, dostane vlastní „+1“ s plným názvem v `title` (výčet je i v detailu).
 */
export type Slot = { side: 1 | -1; tier: 1 | 2 };
export type LabelBall = { ticketId: string; rowId: string; x: number; label: string; stateLabel: string };
export type Cluster = { rowId: string; x: number; ids: string[] };
/** `tier2` = řádky, kde některý popisek potřebuje druhé patro (řádek se zvedne o L2). */
export type Labels = { slots: Record<string, Slot>; clusters: Cluster[]; tier2: Set<string> };

const ORDER: Slot[] = [{ side: 1, tier: 1 }, { side: -1, tier: 1 }, { side: 1, tier: 2 }, { side: -1, tier: 2 }];
/** Vodorovná mezera mezi popisky v jednom slotu (prototyp Linie v3). */
export const GAP = 200;
// shortcut: šířka popisku odhadem 6,4 px na znak při 11,5 px písma; měřit přes canvas.measureText, až budou popisky vyjíždět
export const labelWidth = (b: Pick<LabelBall, "label" | "stateLabel">) => Math.max(b.label.length, b.stateLabel.length) * 6.4 + 8;

/** `upOnly` = řádky s pruhy worktree pod osou: popisky smí jen nad osu (pruhy a jejich jména jsou pod ní). */
export function placeLabels(balls: LabelBall[], selected: string, upOnly: Set<string> = new Set()): Labels {
  const slots: Record<string, Slot> = {};
  const clusters: Cluster[] = [];
  const tier2 = new Set<string>();
  const rows = new Map<string, LabelBall[]>();
  for (const ball of balls) rows.set(ball.rowId, [...(rows.get(ball.rowId) ?? []), ball]);
  for (const [rowId, inRow] of rows) {
    const taken = new Map<Slot, number[]>();
    const order = [...inRow].sort((a, b) => Number(b.ticketId === selected) - Number(a.ticketId === selected) || a.x - b.x);
    const allowed = upOnly.has(rowId) ? ORDER.filter((s) => s.side === -1) : ORDER;
    for (const ball of order) {
      // OP-123CD1.2: vzdálenost od všech popisků slotu (ne jen od posledního), aby vybraná vpravo nevytlačila vzdálené sousedy.
      const slot = allowed.find((s) => (taken.get(s) ?? []).every((x) => Math.abs(ball.x - x) >= GAP));
      if (!slot) { clusters.push({ rowId, x: ball.x, ids: [ball.ticketId] }); continue; }
      slots[ball.ticketId] = slot;
      taken.set(slot, [...(taken.get(slot) ?? []), ball.x]);
      if (slot.tier === 2) tier2.add(rowId);
    }
  }
  return { slots, clusters, tier2 };
}

/** Svislé posuny dvou řádků popisku (název, stav) vůči ose řádku; druhé patro leží o L2 (28 px) dál. */
export function labelOffsets(slot: Slot): { name: number; state: number } {
  const shift = slot.tier === 2 ? 28 * slot.side : 0;
  return slot.side === 1 ? { name: 23 + shift, state: 36 + shift } : { name: -27 + shift, state: -14 + shift };
}

/** Popisek se kreslí od kuličky doprava u levého okraje plátna a doleva u pravého, jinak je vycentrovaný; nikdy nevyjede ven. */
export function labelAnchor(x: number, ball: Pick<LabelBall, "label" | "stateLabel">, plotWidth: number): "start" | "middle" | "end" {
  const half = labelWidth(ball) / 2;
  return x - half < 0 ? "start" : x + half > plotWidth ? "end" : "middle";
}
