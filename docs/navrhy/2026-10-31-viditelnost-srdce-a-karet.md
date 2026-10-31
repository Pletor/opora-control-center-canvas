# Viditelnost srdce a změn na kartách

**Stav: návrh (2026-10-31).** Člověk: „Chci vidět veškeré projevy na kartách, ať si nesou provedené změny
vizuálně. Zároveň nevidím, jak to srdce pracuje, musím důvěřovat, že něco dělá.“

Dnes: kanál srdce (`frontend/layout/heart-channel`) ukáže jen stav (spí / pracuje) a souhrn posledních 5 dávek
**po** jejich konci. Co srdce během dávky dělá, nevidět. Zápisy srdce jsou v záznamu činnosti (`agent: heart`),
ale mezi desítkami dotazů kanceláře a často bez `nodeIds`. Karta (`editor/canvas/card-face`) ukazuje stav
z agent-state, ne co se jí naposled stalo; nové pole `order` (#225) nevidí vůbec.

Bez změny schématu tabulek, brány uzavření karty a dat v `P:\opora-data` mimo API. Jen čtení a zobrazení.

## A. Srdce právě teď (kanál srdce)

- `GET /api/brain/heart/status` přidá `current`: při běžící dávce `{startedAt, inputs}` (vstupy, které ji
  probudily, stejný tvar jako `inputs` v deníku), jinak `null`.
- Sekce **Srdce** v kanálu ukáže při běhu řádek „Pracuje od HH:MM · probudilo: <vstup>“ (zpráva člověka /
  sloučení PR #N / odpověď…) a pod ním **živý seznam kroků dávky**: zápisy záznamu činnosti s `agent: heart`
  od `startedAt`, nejnovější nahoře, každý jako srozumitelná věta (`actionLabel` z `activity-log.ts`: „Návrh
  pořadí 12 karet“, „Úkol do fronty: …“, „Otázka pro vás“), jméno karty, je-li `nodeIds`, a štítek selhání
  u ne-2xx. Dotazování po 4 s jako dnes, jen když je kanál vidět.
- Po konci dávky zůstanou kroky rozbalitelné pod jejím souhrnem (stejný zdroj, rozsah `at` dávky ± trvání).
- Čtení příkazů srdce (`opora_heart.py snapshot`, `ctx`) se nezobrazuje; jen zápisy.

## B. Karta nese své změny (tvář karty)

- **Pořadí:** karta s `order` má v hlavičce odznak `F·PP` (fáze · pozice, `302` → `3·02`), titulek „Pořadí
  podle záměru“. Zdroj `cards[].order` agent-state.
- **Poslední změna:** pod stavovým řádkem jedna tichá řádka „<kdo> · <kdy> · <co>“ (Srdce · 11:51 · pořadí;
  Vy · včera · název; Dělník S.1 · 10:02 · krok s2 hotov) z nejnovějšího zápisu záznamu činnosti s `nodeIds`
  obsahujícím kartu. Klik otevře záznam činnosti s filtrem „Jen vybraná karta“. Zápis mladší než 10 min má
  krátký záblesk obrysu (bez animace při `prefers-reduced-motion`).
- Backend: zápisy, které mění uzly (návrh grafu, přijetí návrhu, zápis architektury, `steps`, `member`,
  `order`, úkol brány s `nodeId`), nesou v záznamu činnosti `nodeIds` dotčených uzlů. Kde je dnes nemají,
  doplní je.
- `GET /api/activity-log/latest-by-node?project&workspace` → `{nodeId: {at, actor, agent, label}}` (jeden
  dotaz pro celé plátno, ne dotaz na kartu).

## Řezy (každý malé PR z čerstvého `main`)

1. **A:** `backend/brain_opora/heart/supervisor.py` (`current`), `frontend/layout/heart-channel` (dílek
   `HeartLive`, logika kroků s testem), README.
2. **B1:** `nodeIds` u zápisů srdce a návrhů grafu + `latest-by-node`, testy vedle modulů.
3. **B2:** `frontend/editor/canvas/card-face`: odznak pořadí a řádka poslední změny, logika s testem, CSS blok
   s příběhovým komentářem.

Ověření každého řezu: cílené `uv run pytest`, `npm test`, `npm run build`, živě na Ample (8740 po restartu).
