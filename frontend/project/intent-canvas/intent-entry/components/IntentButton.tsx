import { intentBadge, type PageIntents } from "../logic/page-intents";
import "../styles/intent-entry.css";

/** Vstup na plátno záměru z karty stránky a z formuláře stránky: stav záměrů projektu (`intents`, null = neznámý) a
 * otevření plátna, které vyřizuje App. */
export type IntentEntry = { intents: PageIntents | null; onOpen: (pageId: string) => void };

/** Tlačítko „Záměr“ s odznakem stavu (bez záměru, čeká, schválený vN, zastaralý). Když stav neznáme, odznak chybí. */
export default function IntentButton({ pageId, entry }: { pageId: string; entry: IntentEntry }) {
  const badge = intentBadge(entry.intents?.get(pageId));
  return <button type="button" className="intent-entry" data-testid={"page-intent-open-" + pageId} title={badge?.title ?? "Otevřít plátno záměru stránky"}
    onClick={() => entry.onOpen(pageId)}>
    Záměr{badge && <span className={`intent-entry__badge intent-entry__badge--${badge.tone}`} data-testid={"page-intent-badge-" + pageId}>{badge.label}</span>}
  </button>;
}
