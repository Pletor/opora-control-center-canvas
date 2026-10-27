// Klávesnice plátna Studia (docs/studio.md §3): šipky posunou výběr na nejbližší kartu daným směrem, Enter sestoupí,
// Backspace vystoupí, Escape zruší výběr. Čistá logika bez Reactu; co se stane, rozhodne rodič.

export type Direction = "left" | "right" | "up" | "down";
export type StudioKeyAction = { kind: "move"; direction: Direction } | { kind: "enter" } | { kind: "up" } | { kind: "clear" } | null;
type Placed = { id: string; x: number; y: number };

const ARROWS: Record<string, Direction> = { ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down" };

export function keyAction(key: string): StudioKeyAction {
  if (key in ARROWS) return { kind: "move", direction: ARROWS[key] };
  if (key === "Enter") return { kind: "enter" };
  if (key === "Backspace") return { kind: "up" };
  if (key === "Escape") return { kind: "clear" };
  return null;
}

/** Bez výběru první karta (nahoře vlevo); jinak nejbližší karta ve směru, boční odchylka se trestá dvojnásobně.
 * Ve směru nic není = výběr zůstane. */
export function nextInDirection(cards: Placed[], current: string | null, direction: Direction): string | null {
  if (!cards.length) return null;
  const from = cards.find((card) => card.id === current);
  if (!from) return [...cards].sort((a, b) => a.y - b.y || a.x - b.x)[0].id;
  let best: string | null = null; let score = Infinity;
  for (const card of cards) {
    if (card.id === from.id) continue;
    const dx = card.x - from.x; const dy = card.y - from.y;
    const ahead = direction === "left" ? -dx : direction === "right" ? dx : direction === "up" ? -dy : dy;
    const side = direction === "left" || direction === "right" ? Math.abs(dy) : Math.abs(dx);
    if (ahead <= 0) continue;
    const value = ahead + 2 * side;
    if (value < score) { score = value; best = card.id; }
  }
  return best ?? from.id;
}
