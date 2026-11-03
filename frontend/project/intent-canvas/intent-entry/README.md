# Vstup na záměr stránky

Tlačítko „Záměr“ (`IntentButton`) na kartě stránky a ve formuláři stránky. Otevře plátno záměru (`onOpen(pageId)`, vyřizuje App: `projectView=intent&page=<id>`). Odznak stavu: bez záměru, čeká, schválený vN, zastaralý; v bublině počet hotových kritérií.

- `logic/page-intents.ts` (+ test): typ odpovědi `GET /api/flow/page-intents?project=` (obal `{pages: [...]}`), čtení, `intentBadge`. Chyba nebo 404 = stav neznámý (`null`): odznak chybí, tlačítko zůstane.
- `logic/use-page-intents.ts`: načte stav při otevření editoru architektury a po změně grafu (`digest`); volá ho `ArchitectureEditor` a hotová data jdou dolů v `intent`.
- `styles/intent-entry.css`, předpona `intent-entry`.
