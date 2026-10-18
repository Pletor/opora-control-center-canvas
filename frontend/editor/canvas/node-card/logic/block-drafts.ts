// Rozepsané texty bloků mimo DOM. Plátno kreslí jen karty v obraze (`CULL_VISIBLE` v board/logic/layer-nodes.ts),
// takže karta, která odjede z obrazu, se odmontuje i s rozepsanou textarea a bez `blur`. Draft proto žije tady,
// v modulové mapě: po návratu karty ho pole převezme, zámek ukládání ho vidí i bez DOM. Nic se tu neukládá na
// server; commit dál dělá jen blur přes handler nahoru. Draft nese `base`, uloženou hodnotu, od které vznikl:
// když se uložená hodnota mezitím změní (jiný zápis, agent), starý draft nad ní neplatí a zahodí se.

export type DraftField = "text" | "title" | `port:${string}`;
type Draft = { value: string; base: string };

const drafts = new Map<string, Draft>();
const SEP = "\u0000";

/** Klíč draftu: karta, blok a pole (`text`, `title` nebo `port:<portId>`). */
export const draftKey = (nodeId: string, blockId: string, field: DraftField) => `${nodeId}${SEP}${blockId}${SEP}${field}`;

/** Rozepsaná hodnota nad daným základem; když základ nesedí, draft se zahodí. */
export function readDraft(key: string, base: string): string | undefined {
  const draft = drafts.get(key);
  if (!draft) return undefined;
  if (draft.base !== base) {
    drafts.delete(key);
    return undefined;
  }
  return draft.value;
}

/** Zapíše rozepsanou hodnotu; hodnota shodná se základem draft smaže (nic rozepsaného není). */
export function writeDraft(key: string, base: string, value: string): void {
  if (value === base) drafts.delete(key);
  else drafts.set(key, { value, base });
}

export function clearDraft(key: string): void {
  drafts.delete(key);
}

/** Má karta nějaký rozepsaný text (i když je zrovna mimo obraz a odmontovaná)? */
export function hasDrafts(nodeId: string): boolean {
  const prefix = nodeId + SEP;
  for (const key of drafts.keys()) if (key.startsWith(prefix)) return true;
  return false;
}

/** Klíče všech draftů (pro testy). */
export function draftKeys(): string[] {
  return [...drafts.keys()];
}
