Kontext karty (kontrakt `docs/kontext-karet-a-index.md` §1 a §3): čistá logika bez Reactu, kterou sdílí plátno, pop-up tvorby, panel vazby i detail karty. Nic tu neukládá ani nenačítá.

`logic/card-context.ts` (+ test `card-context.test.ts` se stejnými případy jako `backend/canvas/test_card_context.py`):

- `effectiveType(node)` — typ workflow jen z předpony v názvu přesně `[research] ` / `[prototype] ` / `[grilling] ` / `[task] ` (malými písmeny, s mezerou), jinak `null`. Neukládá se, název se nemění.
- `cardLayer(node)` — platná uložená `card.layer` (`frontend` / `backend` / `database` / `library`), jinak `null`; krátké štítky FE / BE / DB / Knihovna v `LAYER_LABEL`.
- `effectiveStatus(node, doneConfirmed)` — `done` u uzavřené karty, jinak `card.status`, jinak `null` (neznámé, ne „draft“). `done` se nikdy neukládá.
- `slug(name, fallback)` — předpona typu pryč, bez diakritiky, malá písmena, mimo `[a-z0-9]` pomlčka, sloučené a oříznuté pomlčky; prázdný slug → `fallback` (id).
- `cardPath(nodes, node)` / `cardAddress(nodes, node)` / `formatPath(path)` — názvy předků a karty (`Editor › Pop-up tvorby`) a jejich slugy spojené `/` (`editor/pop-up-tvorby`). Počítá se z aktuálních názvů, kruh ani chybějící rodič se nezacyklí. Adresa nikdy není klíčem ani odkazem; klíčem zůstává `id`.
- `normalizeCard(card)` / `withCard(node, card)` — vypustí prázdné a neplatné klíče; prázdná karta je `undefined` a klíč `card` z uzlu zmizí, ostatní pole uzlu zůstanou beze změny.
- Výčty `CARD_LAYERS`, `CARD_STATUSES`, `CARD_MODELS`, `CARD_EFFORTS` pro formuláře.
