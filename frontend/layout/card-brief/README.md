Záložka **Vybraná karta** sekce Struktura (`layout/structure-panel/`): co agent vybrané karty dostane. Dřív záložka „Vybraná karta“ sekce Agenti (smazaná `layout/agent-navbar/`). Všechno je jen ke čtení: aplikace tu žádný model nespouští a nic nezapisuje — zadání se mění v kartě, v inspektoru.

**Dílky**

- `components/CardBrief.tsx` — stáhne balíček pro model (`GET /api/desktop-v3/node-brief`), složí pohled (`briefSummary`) a vykreslí hlavičku, pět sekcí a dvě tlačítka (Kopírovat zadání pro agenta, Kopírovat odkaz). Bez vybrané karty jen pozve („Vyberte kartu.“). Props jen `{ project, workspace, selectedNodeId, refreshKey }` (otisk plátna + revize plochy skládá App).
- `components/CardBriefHeader.tsx` — jméno karty a tři tiché značky (druh, fáze, otevřeno/uzavřeno), poznámka „Jen ke čtení“.
- `components/CardBriefSections.tsx` — pět sekcí v pořadí balíčku: Cíl a konec, Harness, Smyčka, Předávky, Pracovní prostor.
- `components/CardBriefParts.tsx` — stavební kameny `Section` (barevný tón `SectionTone` z tokenů `--cat-<tón>`), `Kv`, `Check`, `Hand`.

**Logika** (testy vedle)

- `logic/card-brief-view.ts` — defenzivní pohled na cizí JSON balíčku (`briefSummary`, `firstLine`, `truncate`, `phaseLabel`, `kindLabel`, `handoffLink`, `briefJson`).
- `logic/use-node-brief.ts` — jediné čtení ze serveru; pozdní odpověď po přepnutí karty se zahodí.

**Styl**

`styles/card-brief.css`, blok `card-brief`, BEM s příběhovými komentáři, barvy jen z tokenů. Rolování a odsazení dává plocha záložky Struktury.
