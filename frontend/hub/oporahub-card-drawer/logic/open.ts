// Šev mezi plátnem a detailem karty: kdo chce otevřít detail, volá `openCardDrawer`; drawer (nebo App
// přes `setCardDrawerFallback`) se zaregistruje jako příjemce; drawer má přednost před náhradou. Žádný stav, žádné React: jen jedna funkce.
export type CardDrawerTab = "zadani" | "kroky" | "beh" | "review" | "historie";
export type CardDrawerRequest = { nodeId: string; tab?: CardDrawerTab };
type Handler = (request: CardDrawerRequest) => void;

let handler: Handler | null = null;
let fallback: Handler | null = null;

/** Zaregistruje příjemce; vrací odregistraci (odregistruje jen sám sebe). */
export function setCardDrawerHandler(next: Handler): () => void {
  handler = next;
  return () => { if (handler === next) handler = null; };
}

/** Náhrada, dokud žádný drawer není zaregistrovaný (App: přepnout do OporaHubu s detailem karty). */
export function setCardDrawerFallback(next: Handler): () => void {
  fallback = next;
  return () => { if (fallback === next) fallback = null; };
}

/** Otevře detail karty na záložce; `false`, když není drawer ani náhrada. */
export function openCardDrawer(nodeId: string, tab?: CardDrawerTab): boolean {
  const target = handler ?? fallback;
  if (!target || !nodeId) return false;
  target(tab ? { nodeId, tab } : { nodeId });
  return true;
}
