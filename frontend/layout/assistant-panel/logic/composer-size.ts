/** Stejný strop jako backend (`backend/claude_code/assistant/context.py` MAX_TEXT). */
export const MESSAGE_LIMIT = 60000;

/** Od tolika znaků pole ukazuje počítadlo, ať je vidět, kolik zbývá. */
const COUNT_FROM = 2000;

const MIN_HEIGHT = 84; // tři řádky textu
const GROW_SHARE = 0.4; // sbalené pole roste s textem do 40 % výšky panelu
const EXPANDED_SHARE = 0.75; // rozbalené pole zabere tři čtvrtiny panelu

/**
 * Výška pole: sbalené roste s textem od tří řádků do 40 % panelu, rozbalené má pevně 75 % panelu,
 * aby šlo projít celé dlouhé zadání. Když se text nevejde, pole se posouvá uvnitř.
 */
export function fieldHeight(contentHeight: number, panelHeight: number, expanded: boolean) {
  const content = contentHeight + 2;
  const max = Math.max(MIN_HEIGHT, panelHeight * (expanded ? EXPANDED_SHARE : GROW_SHARE));
  const height = expanded ? max : Math.min(Math.max(content, MIN_HEIGHT), max);
  return { height: Math.round(height), scroll: content > height };
}

/** Rozbalit má smysl, až text přeroste sbalené pole, nebo když je pole rozbalené. */
export function canExpand(contentHeight: number, panelHeight: number, expanded: boolean) {
  return expanded || fieldHeight(contentHeight, panelHeight, false).scroll;
}

/** Počítadlo znaků: krátká zpráva žádné, dlouhá „12 345 / 60 000“, přes limit varování. */
export function lengthNote(length: number) {
  if (length < COUNT_FROM) return null;
  const fmt = (n: number) => n.toLocaleString("cs-CZ");
  return { text: `${fmt(length)} / ${fmt(MESSAGE_LIMIT)} znaků`, over: length > MESSAGE_LIMIT };
}
