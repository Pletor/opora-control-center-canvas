/**
 * Kolize popisků kuliček (docs/navrhy/2026-11-06-linie-rebrand.md §6): kulička se v čase nikdy neposune, uhýbá jen
 * její popisek. Přednost má vybraná kulička, pak se zkouší pod · nad · druhé patro pod · druhé patro nad; kdo se nevejde
 * ani do dvou pater, padne do shluku „+N“ (plný výčet je v detailu).
 */
export type Slot = { side: 1 | -1; tier: 1 | 2 };
export type LabelBall = { ticketId: string; rowId: string; x: number; label: string; stateLabel: string };
export type Cluster = { rowId: string; x: number; ids: string[] };
export type Labels = { slots: Record<string, Slot>; clusters: Cluster[] };

const ORDER: Slot[] = [{ side: 1, tier: 1 }, { side: -1, tier: 1 }, { side: 1, tier: 2 }, { side: -1, tier: 2 }];
const GAP = 8;
// shortcut: šířka popisku odhadem 6,4 px na znak při 11,5 px písma; měřit přes canvas.measureText, až budou popisky překrývat
export const labelWidth = (b: Pick<LabelBall, "label" | "stateLabel">) => Math.max(b.label.length, b.stateLabel.length) * 6.4 + GAP;

/** `upOnly` = řádky s pruhy worktree pod osou: popisky smí jen nad osu (pruhy a jejich jména jsou pod ní). */
export function placeLabels(balls: LabelBall[], selected: string, upOnly: Set<string> = new Set()): Labels {
  const slots: Record<string, Slot> = {};
  const clusters: Cluster[] = [];
  const rows = new Map<string, LabelBall[]>();
  for (const ball of balls) rows.set(ball.rowId, [...(rows.get(ball.rowId) ?? []), ball]);
  for (const [rowId, inRow] of rows) {
    const taken = new Map<string, [number, number][]>();
    const order = [...inRow].sort((a, b) => Number(b.ticketId === selected) - Number(a.ticketId === selected) || a.x - b.x);
    const allowed = upOnly.has(rowId) ? ORDER.filter((s) => s.side === -1) : ORDER;
    let open: Cluster | null = null;
    for (const ball of order) {
      const half = labelWidth(ball) / 2, span: [number, number] = [ball.x - half, ball.x + half];
      const slot = allowed.find((s) => !(taken.get(`${s.side}${s.tier}`) ?? []).some(([a, b]) => span[0] < b && a < span[1]));
      if (slot) {
        slots[ball.ticketId] = slot;
        taken.set(`${slot.side}${slot.tier}`, [...(taken.get(`${slot.side}${slot.tier}`) ?? []), span]);
        continue;
      }
      // Nevešel se: přidá se ke shluku, pokud ten leží do šířky popisku, jinak začne nový.
      if (open && ball.x - open.x <= half * 2) open.ids.push(ball.ticketId);
      else clusters.push(open = { rowId, x: ball.x, ids: [ball.ticketId] });
    }
  }
  return { slots, clusters };
}

/** Svislé posuny dvou řádků popisku (název, stav) vůči ose řádku; druhé patro nese jen název. */
export function labelOffsets(slot: Slot): { name: number; state: number | null } {
  if (slot.tier === 1) return slot.side === 1 ? { name: 23, state: 36 } : { name: -27, state: -14 };
  return slot.side === 1 ? { name: 50, state: null } : { name: -44, state: null };
}
