/**
 * Vložený dlouhý text jako dlaždice nad polem pro zprávu (jako příloha). Pole zůstane volné pro
 * vlastní pokyn a při odeslání se pokyn a dlaždice složí do jedné zprávy. Tužka dlaždici vrátí do pole.
 */
export type PastedBlock = { id: string; text: string };

const MIN_CHARS = 1500;
const MIN_LINES = 20;
const PREVIEW_CHARS = 140;

/** Dlaždicí se stane vložení delší než 1 500 znaků nebo 20 řádků; kratší jde rovnou do pole. */
export function isLongPaste(text: string) {
  return text.length >= MIN_CHARS || text.split("\n").length >= MIN_LINES;
}

/** Náhled na dlaždici: začátek textu bez zalomení řádků. */
export function pastePreview(text: string) {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > PREVIEW_CHARS ? `${flat.slice(0, PREVIEW_CHARS)}…` : flat;
}

let counter = 0;
export function newBlock(text: string): PastedBlock {
  counter += 1;
  return { id: `paste-${Date.now().toString(36)}-${counter}`, text };
}

/**
 * Jedna zpráva pro asistenta: nejdřív napsaný pokyn (lomítkový příkaz tak zůstane na začátku),
 * pak každá dlaždice v označeném bloku, aby model poznal, kde vložený text začíná a končí.
 */
export function composeMessage(text: string, blocks: PastedBlock[]) {
  const head = text.trim();
  if (!blocks.length) return head;
  const body = blocks.map((b, i) => `<vlozeny_text cislo="${i + 1}">\n${b.text.trim()}\n</vlozeny_text>`);
  return [head, ...body].filter(Boolean).join("\n\n");
}

const BLOCK = /\n*<vlozeny_text cislo="\d+">\n([\s\S]*?)\n<\/vlozeny_text>/g;

/** Odeslaná zpráva zpátky na pokyn a vložené texty, aby je konverzace ukázala sbalené jako dlaždice. */
export function splitMessage(message: string) {
  const blocks = [...message.matchAll(BLOCK)].map((m) => m[1]);
  return { text: message.replace(BLOCK, "").trim(), blocks };
}

/** Pole po kliknutí na tužku: text dlaždice se přidá za to, co už je napsané. */
export function withBlockText(value: string, block: PastedBlock) {
  return value.trim() ? `${value.replace(/\s+$/, "")}\n\n${block.text}` : block.text;
}
