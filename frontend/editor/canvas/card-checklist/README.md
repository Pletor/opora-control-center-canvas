Kontrolní pás karty: deset polí ano / ne (cíl, hotovo, text, bloky, vazby, zdroj, kontroly, pipeline, důkazy, předávka).

- Počítá server (`backend/editor/agent_packet/card_checklist.py`, `GET /api/desktop-v3/card-checklist`); stejný pás dostane agent v `node-brief.checklist` a `frontier` řádky v `missing`.
- `logic/card-checklist.ts` — typy, načtení vrstvy (`useCardChecklist`), souhrn oblasti (`areaSummary`), obálka předávky na vazbě (`handoffMark`).
- `components/CardChecklist.tsx` — pás pod hlavičkou karty (tooltip = co doplnit a kam); `AreaSummary.tsx` — pruhy pod štítkem oblasti.
- Vazba mezi kartami nese obálku: „✉ předáno“ (zpráva na vazbě je), „✉ chybí předávka“ (zdroj je hotový, zpráva chybí).
- Nevybraná karta je kompaktní (`node-card--compact`): podrobnosti a editory má vybraná karta a panel detailu.
