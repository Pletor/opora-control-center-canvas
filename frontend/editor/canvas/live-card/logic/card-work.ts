// „Předat do Kanceláře“: předvyplnění formuláře Velína (`LinieWorkForm`) z živé karty a tělo `POST /api/pletor/linie/work`.
import type { LiveCard } from "./live-card-types";

/** Pole formuláře z karty: název, záměr (cesta + další krok), kritéria hotovo z vize (řádek = kritérium). Větev zadá člověk. */
export function workDraft(card: LiveCard) {
  const path = [...card.crumbs, card.title].join(" › ");
  return {
    title: card.title,
    essence: card.next ? `${path}: ${card.next.text}` : path,
    build: card.next?.text ?? "",
    doneCriteria: (card.truths.vision?.items ?? []).map(item => item.text.trim()).filter(Boolean).join("\n"),
  };
}

/** Tělo formuláře + vazba na kartu (`LinieWorkIn.cardId`); server ověří, že uzel v prostoru existuje. */
export const workBody = (form: object, nodeId: string) => ({ ...form, cardId: nodeId });
