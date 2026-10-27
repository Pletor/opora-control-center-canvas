// Nabídka vazby z portu: kam ji položit, kam položit novou kartu a kdy je stisk portu klik, ne tah.
// Nabídka stojí vpravo od výstupního portu, aby nikdy nepřekryla vstupy zdrojové karty (ty jsou vlevo);
// když vpravo není místo, sedne pod kartu, případně nad ni. Bez Reactu; test vedle.

export type Box = { x: number; y: number; w: number; h: number };

/** Rozměr nabídky, se kterým počítá umístění; CSS ho drží jako `width` a `max-height` (port-menu.css). */
export const MENU_SIZE = { w: 300, h: 380 };
const GAP = 10;
const MARGIN = 8;

const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(value, Math.max(low, high)));

/**
 * Levý horní roh nabídky v souřadnicích plochy plátna (`stage` = 0,0 vlevo nahoře). `port` je úchyt výstupu,
 * `card` karta zdroje. Pořadí: vpravo od portu → pod kartou → nad kartou; vždy uvnitř plochy.
 */
export function menuPosition(port: Box, card: Box, stage: { w: number; h: number }, size = MENU_SIZE): { x: number; y: number } {
  const right = port.x + port.w + GAP;
  if (right + size.w <= stage.w - MARGIN) return { x: right, y: clamp(port.y - 24, MARGIN, stage.h - size.h - MARGIN) };
  const x = clamp(card.x + card.w - size.w, MARGIN, stage.w - size.w - MARGIN);
  const below = card.y + card.h + GAP;
  const y = below + size.h <= stage.h - MARGIN || card.y - GAP - size.h < MARGIN ? below : card.y - GAP - size.h;
  return { x, y: clamp(y, MARGIN, stage.h - size.h - MARGIN) };
}

/**
 * Tělesa tak, jak s nimi počítá server při vkládání plánu (`backend/canvas/canvas_plan_layout.py`): karta
 * 360 × 240, komentář 240 × 160, oblast podle `size`, mezi tělesy mezera 96. Navržené místo, které podle
 * serveru koliduje, by server posunul jinam; proto ho počítáme stejně a nová karta zůstane, kam ji dáme.
 */
export const PLAN_CARD = { w: 360, h: 240 };
const PLAN_COMMENT = { w: 240, h: 160 };
export const PLAN_GAP = 96;

type PlanBody = { kind: string; x: number; y: number; size?: { w: number; h: number } };
export function planBox(node: PlanBody): Box {
  const size = node.kind === "area" ? node.size ?? PLAN_CARD : node.kind === "comment" ? PLAN_COMMENT : PLAN_CARD;
  return { x: node.x, y: node.y, w: size.w, h: size.h };
}

const clear = (a: Box, b: Box) => a.x + a.w + PLAN_GAP <= b.x || b.x + b.w + PLAN_GAP <= a.x || a.y + a.h + PLAN_GAP <= b.y || b.y + b.h + PLAN_GAP <= a.y;

/**
 * Poloha nové karty (souřadnice mapy): vpravo od zdroje ve stejné výšce, o těleso a mezeru dál; leží-li
 * tam jiné těleso, sjede o řádek níž, dokud není volno (nejvýš 40 řádků, pak zůstane na posledním místě).
 */
export function newCardPosition(source: { x: number; y: number }, others: Box[]): { x: number; y: number } {
  const x = Math.round(source.x + PLAN_CARD.w + PLAN_GAP);
  let y = Math.round(source.y);
  for (let row = 0; row < 40; row += 1) {
    if (others.every((other) => clear({ x, y, ...PLAN_CARD }, other))) break;
    y += PLAN_CARD.h + PLAN_GAP;
  }
  return { x, y };
}

/** Práh pohybu (px na obrazovce): stisk a puštění portu blíž než práh je klik (nabídka), dál je tah vazby. */
export const CLICK_SLOP = 5;

export function isPortClick(down: { x: number; y: number } | null, up: { x: number; y: number }): boolean {
  return !!down && Math.hypot(up.x - down.x, up.y - down.y) < CLICK_SLOP;
}
