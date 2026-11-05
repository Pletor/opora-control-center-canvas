/**
 * Síto trvalého poslechu (přepínač Poslech): mikrofon stojí vedle reproduktorů a slyší i okolí, proto se
 * Pletorovi pošle jen věta, která dává smysl. Krátký šum (pod 2 znaky) a stejná věta do 2 s se zahodí;
 * v režimu „jen na oslovení“ projde jen věta s oslovením (Pletore, Pletor, Jarvisi), které se z textu odstraní.
 */

export const WAKE_WORDS = ["pletore", "pletor", "jarvisi", "jarvis"];
export const MIN_CHARS = 2;
export const DUPLICATE_MS = 2000;

/** Bez diakritiky a velikosti písmen: „Pletoře“ i „PLETORE“ jsou totéž oslovení. */
export function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
}

const bare = (word: string) => fold(word).replace(/[^\p{L}\p{N}]/gu, "");

/** Věta bez oslovení, nebo `null`, když oslovení v ní není. */
export function stripWake(text: string): string | null {
  const words = text.trim().split(/\s+/);
  const kept = words.filter((word) => !WAKE_WORDS.includes(bare(word)));
  if (kept.length === words.length) return null;
  return kept.join(" ").replace(/^[\s,.;:!?–-]+/, "").trim();
}

export type Heard = { text: string; at: number };

/** Co z hotové věty poslat Pletorovi (`null` = nic). `last` je předchozí slyšená věta a čas (ms). */
export function heardCommand(text: string, { wakeOnly, last, now }: { wakeOnly: boolean; last: Heard | null; now: number }): string | null {
  const clean = text.trim();
  if (clean.length < MIN_CHARS) return null;
  if (last && now - last.at < DUPLICATE_MS && fold(last.text) === fold(clean)) return null;
  if (!wakeOnly) return clean;
  const command = stripWake(clean);
  return command && command.length >= MIN_CHARS ? command : null;
}
